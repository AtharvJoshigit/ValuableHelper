# Audit Report: Thought Leaks & Persistence
**Date:** 2026-02-26
**Scope:** `agent.py`, `orchestrator.py`, `provider.py`, `adapter.py`

## Executive Summary
I performed a static analysis to check if "internal thoughts" (reasoning traces) are leaking into user responses or being mishandled.

**Status:** **No active leaks to the user found**, but a **Critical Bug** causes the model to *forget* its own thoughts during history reconstruction (Context Loss).

---

## 1. Critical Bug: Context Loss in `adapter.py`
**Location:** `src/engine/providers/google/adapter.py` (Line ~250)
**Issue:** A typo in the attribute name prevents thoughts from being replayed to the model in subsequent turns.

```python
# Current Code (Bugged)
if hasattr(msg, ' thought_text') and msg.thought_text:  # <--- Leading space in string
    parts.append(types.Part(thought=True, text=msg.thought_text))

# Correct Code
if hasattr(msg, 'thought_text') and msg.thought_text:
    parts.append(types.Part(thought=True, text=msg.thought_text))
```

**Impact:**
- When the system reconstructs history (e.g., after a restart or if `_raw_provider_content` is missing), the `thought_text` is ignored.
- The model loses the context of *why* it made a decision in the previous turn.

## 2. Leak Analysis (User Facing)
**Location:** `src/engine/providers/google/provider.py`
**Finding:** **Safe.**

The provider explicitly separates "thought" parts from "text" parts:
```python
if getattr(part, "thought", False) and part.text:
    reasoning_text = part.text
    # ...
    continue  # <--- Skips adding to text_parts
```
The final `AgentResponse` is built only from `text_parts`. Therefore, thoughts do **not** leak into the final string returned to the user.

## 3. Architecture Note: Raw Content vs. Reconstruction
**Observation:**
The system prefers using `msg._raw_provider_content` (the original Google object) if available.
- **Pros:** Preserves exact binary data (like `thought_signature`).
- **Cons:** If the agent restarts, `_raw_provider_content` is lost (it's not in the DB). The system falls back to the manual reconstruction logic in `adapter.py`.

**Risk:** Because the manual reconstruction path had the typo (Item 1), the system behavior degrades silently after a restart (thoughts disappear).

## Action Plan
1.  **Fix Typo:** Remove the leading space in `adapter.py`.
2.  **Verify Replay:** Ensure `thought_signature` is correctly attached to `types.Part` (logic appears correct, but requires the typo fix to be reachable in some paths).
