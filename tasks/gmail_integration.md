# Gmail Service Integration & Fix

## Context
We moved the Gmail service files from the nested `src/src` mess to `src/services/gmail`. Now we need to properly expose them as a Tool for the MainAgent and clean up the old files.

## Status
- [x] Create `src/services/gmail/` directory
- [x] Move/Create `auth.py` and `service.py` in `src/services/gmail/`
- [x] **Critical**: `src/tools/gmail_tool.py` needs to be written/verified to match the `Tool` interface.
- [x] **Critical**: Register tool in `src/agents/main_agent.py`.
- [x] Cleanup: Delete `src/src/` folder.

## Action Plan (Next Session)

1. **Verify Tool Interface**
   - Read `src/engine/registry/library/filesystem_tools.py` to understand how to subclass `Tool`.
   - Ensure `src/tools/gmail_tool.py` follows this pattern (inputs, outputs, execute method).

2. **Implement `GmailTool`**
   - It should expose at least:
     - `search_emails(query, limit)`
     - `read_email(message_id)`
     - `send_email(to, subject, body)`
   - It needs to handle the OAuth flow gracefully (asking user to check console if needed).

3. **Register in `MainAgent`**
   - Edit `src/agents/main_agent.py`.
   - Import `GmailTool`.
   - Add `registry.register(GmailTool())` in `_get_registry()`.

4. **Cleanup**
   - `rm -rf src/src`

5. **Test**
   - Run the bot.
   - User command: "Check my unread emails".
   - Verify it triggers the auth flow (if token missing) or returns emails.