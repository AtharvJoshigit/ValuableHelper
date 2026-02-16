# engine/core/summarizer.py
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from engine.core.types import Message, Role
from engine.core.provide import get_provider

logger = logging.getLogger(__name__)

class MemorySummarizer:
    """
    Service responsible for summarizing conversation history.
    Generates both short (contextual) and long (archival) summaries.
    """
    
    SHORT_SUMMARY_PROMPT = """You are a memory compression expert. Analyze the conversation below and create a CONCISE summary under 200 tokens.

Focus on:
- Key facts mentioned (names, dates, preferences, decisions)
- Important decisions or agreements made
- Critical context needed for future conversations
- User's goals, constraints, or requirements

Format as bullet points for easy scanning. Be extremely concise.

Conversation to summarize:
{conversation}

SHORT SUMMARY (under 200 tokens):"""

    LONG_SUMMARY_PROMPT = """You are creating a detailed narrative memory for long-term storage. Analyze the conversation and create a comprehensive summary.

Include:
- Full narrative of what was discussed
- Specific details, technical information, and context
- User preferences, decisions, and reasoning
- Action items or follow-ups mentioned
- Emotional tone and relationship dynamics
- Any specialized knowledge or domain context

Also rate the IMPORTANCE of this conversation (1-10):
- 1-3: Casual chat, low value
- 4-6: Normal conversation, moderate value  
- 7-8: Important decisions or information
- 9-10: Critical information, major milestones

Conversation to summarize:
{conversation}

Respond in JSON format:
{{
  "summary": "detailed narrative summary here",
  "importance": <1-10>,
  "key_topics": ["topic1", "topic2"],
  "action_items": ["item1", "item2"]
}}"""

    def __init__(self, agent_id: str, model: str = "gemini-3-flash-preview"):
        self.agent_id = agent_id
        # Use a lightweight model for summarization
        self.provider = get_provider(
            "google",
            model_id=model,
            temperature=0.3,
            max_tokens=1000
        )
    
    def _format_messages(self, messages: List[Message]) -> str:
        """Convert messages to readable text format."""
        formatted = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # Skip system messages in summaries
            
            role_name = msg.role.value.upper()
            content = msg.content or ""
            
            # Include tool calls in summary
            if msg.tool_calls:
                tool_names = [tc.name for tc in msg.tool_calls]
                content += f" [Used tools: {', '.join(tool_names)}]"
            
            # Include tool results
            if msg.tool_results:
                results = [f"{tr.name}: {str(tr.result)[:100]}" for tr in msg.tool_results]
                content += f" [Results: {'; '.join(results)}]"
            
            formatted.append(f"{role_name}: {content}")
        
        return "\n".join(formatted)
    
    async def summarize_conversations(
        self, 
        messages: List[Message],
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate both short and long summaries of the conversation.
        
        Returns:
            Dict with 'short', 'long', 'importance', and 'metadata' keys
        """
        if not messages:
            return {
                "short": "",
                "long": "",
                "importance": 1,
                "metadata": {}
            }
        
        conversation_text = self._format_messages(messages)
        
        try:
            # Generate short summary
            short_response = await self.provider.generate(
                history=[Message(
                    role=Role.USER,
                    content=self.SHORT_SUMMARY_PROMPT.format(conversation=conversation_text)
                )],
                tools=[]
            )
            short_summary = (short_response.content or "").strip()
            
            # Generate long summary with metadata
            long_response = await self.provider.generate(
                history=[Message(
                    role=Role.USER,
                    content=self.LONG_SUMMARY_PROMPT.format(conversation=conversation_text)
                )],
                tools=[]
            )
            
            # Parse JSON response
            import json
            long_data = json.loads(long_response.content or "{}")
            
            return {
                "short": short_summary,
                "long": long_data.get("summary", ""),
                "importance": long_data.get("importance", 5),
                "metadata": {
                    "key_topics": long_data.get("key_topics", []),
                    "action_items": long_data.get("action_items", []),
                    "message_count": len(messages),
                    "agent_name": agent_name,
                    "summarized_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Summarization failed for agent {self.agent_id}: {e}")
            # Fallback to simple summary
            return {
                "short": f"Conversation with {len(messages)} messages (summarization failed)",
                "long": conversation_text[:500],
                "importance": 5,
                "metadata": {}
            }