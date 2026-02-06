# Telegram Bot Modernization Plan

## Overview
The goal is to transform `src/services/telegram_bot` from a legacy research-bot interface into the primary **Human-in-the-Loop (HITL)** interface for the Universal Agent Framework. The bot will allow the user to chat with the `MainAgent`, receive tool execution requests, and grant/deny permissions securely.

## Current State Analysis
- **`config.py`**: Contains mixed privacy logic. Needs simplification.
- **`messages.py`**: Good centralization, needs updates for new agent states.
- **`bot.py`**: Monolithic, contains dead code (`AIResearchHandler`), lacks async stream handling for agent responses.
- **Entry Point**: `src/main.py` is missing or disconnected.

## Phase 1: Configuration & Hygiene
- [x] **Refactor `config.py`**: 
    - Simplify auth to `USER_ID` whitelist (most secure/practical for personal assistant).
    - Load tokens/secrets strictly from environment variables.
- [x] **Clean `messages.py`**:
    - Remove legacy "Research" command messages.
    - Add new messages for "Tool Permission Requested" and "Agent Thinking".

## Phase 2: Core Bot Logic (`bot.py`)
- [x] **Remove Legacy Code**: Delete `AIResearchHandler` and `researchTopic` commands.
- [x] **Integrate `MainAgent`**: 
    - Initialize `MainAgent` on `/start`.
    - Persist agent instance in `context.user_data`.
- [x] **Async Message Handling**:
    - Use `agent.stream()` instead of `run()` to provide real-time feedback.
    - Implement a "Typing..." indicator or periodic status updates (e.g., "🔧 Executing tool...").

## Phase 3: Human-in-the-Loop (HITL) Protocol
**Objective**: When the Agent needs to execute a sensitive tool (File Write, Shell Command), it must pause and ask the user via Telegram.

### Design Pattern
1. **Agent Side**: 
    - The `SystemOperator` or `CoderAgent` tools return a special "Permission Required" signal or the Agent itself pauses.
    - *Simpler MVP Approach*: The Agent just asks "I need to run X, can I?" and waits for the user's text reply "Yes".
2. **Bot Side**:
    - Forward the user's "Yes/No" back to the agent's memory.
    - (Future) Render Inline Buttons [✅ Approve] [❌ Deny] that inject the specific permission token.

## Phase 4: Entry Point & Deployment
- [x] **Create `src/main.py`**: A clean entry point that loads env vars and starts the bot polling.
- [ ] **Docker/Process Manager**: Ensure the bot auto-restarts on crash.

## Phase 5: Coder Agent Optimization
- [ ] **Performance Tuning**: Increase timeout for `CoderAgent` operations.
- [ ] **Context Strategy**: Implement "Smart Context" where the Coder Agent only receives relevant file snippets, not full dumps, to avoid timeouts.