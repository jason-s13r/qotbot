# Test Plan: LLM Conversation Handling and Streaming

## Objective
Validate that conversational LLM responses, optional thought capture, and streaming delivery work correctly while preserving behavior for classifier, summariser, and image describer.

## Test Matrix
1. Chatter non-stream baseline
- Input: Standard chat message with streaming disabled.
- Expectation: One conversational response message is sent; tools still available for supplemental actions.

2. Chatter model streaming + Telegram progressive delivery
- Input: Standard chat message with both streaming flags enabled.
- Expectation: Response appears progressively via edits/chunks and final message is coherent.

3. Chatter streaming fallback
- Input: Induced stream interruption or Telegram edit failure.
- Expectation: System falls back to single final send with no duplicate spam.

4. Chatter mixed tool workflow
- Input: Prompt that requires both conversational response and side-effect tool (for example poll/file).
- Expectation: Conversational text appears as primary reply; tool artifact sent separately.

5. Thought capture disabled
- Input: Any chatter/classifier/summariser/image-describer run with thought capture off.
- Expectation: No thought records persisted.

6. Thought capture enabled for chatter only
- Input: Chatter run with thought capture enabled only for chatter.
- Expectation: Chatter thoughts persisted and retrievable; other agents store none.

7. Thought capture enabled for classifier
- Input: Classifier run on ambiguous message.
- Expectation: approve/reject outcome unchanged; optional thought record stored for diagnostics.

8. Thought capture enabled for summariser
- Input: /summary and /daily runs.
- Expectation: Summary output and file send unchanged; optional thought record stored.

9. Thought capture enabled for image describer
- Input: Image description run with difficult image.
- Expectation: Final description persisted as before; optional thought record stored.

10. /thoughts authorization
- Input: Owner/admin and non-owner attempts to read thought records.
- Expectation: Authorized users can query by filters; unauthorized users denied.

11. /thoughts filtering and pagination
- Input: Query by chat_id, message_id, agent_type, time range with large dataset.
- Expectation: Correct subset returned with stable ordering and pagination.

12. Public behavior regression
- Input: Existing normal flows across response/classification/summary/image paths.
- Expectation: No regressions in message processing, approvals, summaries, or media annotation.

## Observability Checks
- Confirm logs for stream lifecycle include run_id, chat_id, message_id, state transitions.
- Confirm metrics for stream fallback rate and edit cadence are emitted.
- Confirm thought-write logs include agent_type and size, without sensitive plaintext dumps.

## Exit Criteria
- All matrix scenarios pass in staging.
- No unauthorized thought access is observed.
- Chatter streaming remains within acceptable latency and error budgets.
- Non-chatter agents maintain functional parity with pre-epic behavior.
