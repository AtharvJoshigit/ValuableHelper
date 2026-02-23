# engine/core/summarizer.py
"""
MemorySummarizer — progressive, turn-aware conversation summarizer.

Changes from previous version
------------------------------
- Accepts `previous_summary` so each cycle builds incrementally on the last
  short summary rather than re-processing the entire history.
- Uses msg.text instead of msg.content (schema alignment).
- Tool call/result formatting uses tool_call.name / tool_result.name (schema alignment).
- SHORT_SUMMARY_PROMPT updated to incorporate the prior summary when present.
- JSON parsing is hardened with a fallback strip of markdown fences.
- _format_messages skips Role.SYSTEM (aleady excluded but now explicit).
- summarize_conversations signature matches MemoryManager's call site:
    previous_summary: Optional[str] = None
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.core.provide import get_provider
from engine.schemas.message import Message, MessageKind, Role
from engine.schemas.response import AgentResponse

logger = logging.getLogger(__name__)


class MemorySummarizer:
    """
    Generates short (working memory) and long (archival) summaries.

    Short summary  — replaces itself every cycle via upsert; fed into the
                     fused system prompt.  Built progressively from:
                         previous_short_summary + new archivable turns

    Long summary   — append-only; stored for RAG semantic recall.
    """

    # ------------------------------------------------------------------ #
    # Prompts                                                              #
    # ------------------------------------------------------------------ #

    _SHORT_PROMPT_NO_PRIOR = """\
You are a memory compression expert. Analyze the conversation below and produce \
a CONCISE summary in under 200 tokens.

Focus on:
- Key facts (names, dates, preferences, decisions)
- Important decisions or agreements
- User goals, constraints, or requirements
- Any unresolved action items

Format as tight bullet points. Be extremely concise — every word must earn its place.

Conversation:
{conversation}

SHORT SUMMARY (≤200 tokens):"""

    _SHORT_PROMPT_WITH_PRIOR = """\
You are a memory compression expert. You have an existing running summary and a \
new batch of conversation turns. Merge them into a single updated summary in \
under 250 tokens.

Rules:
- Preserve every still-relevant fact from the prior summary.
- Add new facts, decisions, and context from the new turns.
- Drop outdated or superseded information.
- Format as tight bullet points.

Prior summary:
{prior_summary}

New conversation turns:
{conversation}

UPDATED SHORT SUMMARY (≤250 tokens):"""

    _LONG_PROMPT = """\
You are creating a detailed narrative memory for long-term archival storage.

Include:
- Full narrative of what was discussed
- Specific technical details and context
- User preferences, decisions, and reasoning
- Action items or follow-ups mentioned
- Domain-specific knowledge surfaced

Rate the IMPORTANCE of this batch (1–10):
  1–3 : Casual chat, low long-term value
  4–6 : Normal conversation, moderate value
  7–8 : Important decisions or information
  9–10: Critical information, major milestones

Conversation:
{conversation}

Respond with ONLY valid JSON — no markdown fences, no extra keys:
{{
  "summary": "<detailed narrative>",
  "importance": <1-10>,
  "key_topics": ["topic1", "topic2"],
  "action_items": ["item1", "item2"]
}}"""

    # ------------------------------------------------------------------ #
    # Init                                                                 #
    # ------------------------------------------------------------------ #

    def __init__(
        self,
        agent_id: str,
        model: str = "gemini-2.5-pro",
    ):
        self.agent_id = agent_id
        self.provider = get_provider(
            "google",
            model_id=model,
            temperature=0.3,
            max_tokens=1200,
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def summarize_conversations(
        self,
        messages: List[Message],
        agent_name: Optional[str] = None,
        previous_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate short and long summaries for a batch of messages.

        Parameters
        ----------
        messages
            New archivable messages (already outside the active context window).
            System messages and thought_text are ignored.
        agent_name
            Used in metadata only.
        previous_summary
            The current short summary text (if any).  When provided, the new
            short summary is built as a merge of prior + new turns rather than
            from scratch.  This is the progressive-summarization path.

        Returns
        -------
        Dict with keys: short, long, importance, metadata
        """
        if not messages:
            return {"short": "", "long": "", "importance": 1, "metadata": {}}

        conversation_text = self._format_messages(messages)

        try:
            short_summary = await self._generate_short(
                conversation_text=conversation_text,
                previous_summary=previous_summary,
            )
            long_data = await self._generate_long(conversation_text)

            return {
                "short": short_summary,
                "long": long_data.get("summary", ""),
                "importance": long_data.get("importance", 5),
                "metadata": {
                    "key_topics": long_data.get("key_topics", []),
                    "action_items": long_data.get("action_items", []),
                    "message_count": len(messages),
                    "agent_name": agent_name,
                    "summarized_at": datetime.now(timezone.utc).isoformat(),
                },
            }

        except Exception as e:
            logger.exception(
                "Summarization failed for agent %s — using fallback.", self.agent_id
            )
            logger.exception("Failed for Exception: %s", e)
            fallback_short = (
                f"[Merged] {previous_summary}\n\n[New] {conversation_text[:300]}"
                if previous_summary
                else conversation_text[:300]
            )
            return {
                "short": fallback_short,
                "long": conversation_text[:800],
                "importance": 5,
                "metadata": {
                    "message_count": len(messages),
                    "agent_name": agent_name,
                    "summarized_at": datetime.now(timezone.utc).isoformat(),
                },
            }

    # ------------------------------------------------------------------ #
    # Private generation helpers                                           #
    # ------------------------------------------------------------------ #

    async def _generate_short(
        self,
        conversation_text: str,
        previous_summary: Optional[str],
    ) -> str:
        if previous_summary:
            prompt = self._SHORT_PROMPT_WITH_PRIOR.format(
                prior_summary=previous_summary,
                conversation=conversation_text,
            )
        else:
            prompt = self._SHORT_PROMPT_NO_PRIOR.format(
                conversation=conversation_text,
            )

        response = await self.provider.call_model(
            history=[Message(role=Role.USER, text=prompt)],
            tools=[],
        )
        logger.info("short summery Response : %s", response)
        return self._extract_text(response).strip()

    async def _generate_long(self, conversation_text: str) -> Dict[str, Any]:
        prompt = self._LONG_PROMPT.format(conversation=conversation_text)

        response = await self.provider.call_model(
            history=[Message(role=Role.USER, text=prompt)],
            tools=[],
        )
        logger.info("long summery Response : %s", response)
        raw = self._extract_text(response).strip()
        return self._parse_json(raw)

    # ------------------------------------------------------------------ #
    # Formatting                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_messages(messages: List[Message]) -> str:
        """
        Render a message list as readable plain text for the LLM prompts.

        Rules:
        - System messages are skipped (never summarized).
        - thought_text / reasoning_text are skipped (debug artifacts).
        - Tool calls are noted by name only (arguments omitted for brevity).
        - Tool results are truncated to 150 chars to keep prompts compact.
        """
        lines: List[str] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue

            # Map internal roles to readable labels
            if msg.role == Role.USER and msg.kind == MessageKind.TOOL_RESULT:
                label = "TOOL_RESULT"
            elif msg.role == Role.MODEL:
                label = "ASSISTANT"
            else:
                label = msg.role.value.upper()

            parts: List[str] = []

            if msg.text:
                parts.append(msg.text)

            if msg.tool_calls:
                names = [tc.name for tc in msg.tool_calls]
                parts.append(f"[Tool calls: {', '.join(names)}]")

            if msg.tool_results:
                snippets = [
                    f"{tr.name}: {str(tr.result)[:150]}"
                    for tr in msg.tool_results
                ]
                parts.append(f"[Tool results: {'; '.join(snippets)}]")

            if parts:
                lines.append(f"{label}: {' '.join(parts)}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Utilities                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text(provider_output: Any) -> str:
        """
        Pull plain text out of whatever the provider returns.
        Handles ProviderOutput, AgentResponse, or a bare string.
        """
        
        if isinstance(provider_output, AgentResponse):
            return provider_output.response_text
        # ProviderOutput shape from GoogleProvider
        if hasattr(provider_output, "agent_response"):
            return provider_output.agent_response.response_text or ""
        # AgentResponse directly
        if hasattr(provider_output, "response_text"):
            return provider_output.response_text or ""
        # Legacy .content path
        if hasattr(provider_output, "content"):
            return provider_output.content or ""
        return str(provider_output)

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        """
        Parse JSON from the LLM response.
        Strips markdown fences (```json ... ```) if the model added them.
        Falls back to an empty dict on failure.
        """
        text = raw.strip()

        # Strip common markdown fence patterns
        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
                break
        if text.endswith("```"):
            text = text[: -3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse long-summary JSON; raw response: %.200s", raw
            )
            return {}