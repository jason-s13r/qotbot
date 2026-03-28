# Test Plan: Owner-Only LLM Tools

## Objective
Validate that owner-only tools are correctly gated by sender identity without breaking existing public tool behavior.

## Test Matrix
1. Owner path
- Input: Message from `TELEGRAM_BOT_OWNER`.
- Expectation: Owner tool schemas available and callable.

2. Non-owner path
- Input: Message from any other sender.
- Expectation: Owner tools absent; public tools remain available.

3. Sender lookup failure
- Input: Missing/deleted message row or retrieval error.
- Expectation: Owner tools not mounted; response still completes with public tools.

4. Handler-level auth defense
- Input: Direct invocation attempt with `is_owner=false` context.
- Expectation: Sensitive handler rejects execution.

5. Public tool regression
- Input: Typical non-owner conversation using existing tools.
- Expectation: send_message/web/logs/date/todo/woolworths/lolcryption still work.

6. Side-effect controls
- Input: Repeated owner-tool calls in one response loop.
- Expectation: call limits and dedupe prevent unsafe repetition.

## Observability Checks
- Confirm auth decision log includes `chat_id`, `message_id`, `sender_id`, `is_owner`.
- Confirm owner-tool action logs omit secrets and sensitive payloads.

## Exit Criteria
- All matrix scenarios pass.
- No unauthorized owner-tool availability observed.
- No breakage in non-owner public tool flows.
