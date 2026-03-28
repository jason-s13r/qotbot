# Tasks: LLM Conversation Handling and Streaming

## Phase 1: Contracts and Data Model
1. Define conversation result envelope shared across agent invocations.
2. Decide thought payload format and redaction policy.
3. Add DB schema for thought records keyed by chat_id/message_id/run_id/agent_type.
4. Add retention policy fields and cleanup strategy.

## Phase 2: Chatter Response Model
1. Update chatter prompt/contract to produce primary conversational final text.
2. Preserve tool execution support for supplemental side effects.
3. Define ordering rules between conversational text and tool side effects.
4. Add fallback behavior when no final text is returned.

## Phase 3: LLM Streaming Integration
1. Add streaming invocation path in LLM agent layer.
2. Emit stream events (delta, completed, error) to response worker.
3. Keep non-streamed invocation path as default-compatible fallback.
4. Add robust timeout/cancel handling.

## Phase 4: Telegram Progressive Delivery
1. Implement response message lifecycle (initial placeholder, edit updates, final commit).
2. Add cadence controls to avoid Telegram flood/rate issues.
3. Support fallback to single send when edits fail.
4. Ensure tool-generated messages remain distinct from conversational response message.

## Phase 5: Thought Capture and Retrieval
1. Gate thought capture with config flags (global and optional per agent type).
2. Persist thoughts for enabled agents with size limits and truncation policy.
3. Implement /thoughts retrieval command with owner/admin authorization.
4. Add filters for chat, message, agent_type, and time window.

## Phase 6: Non-Chatter Agent Compatibility
1. Classifier: keep approve/reject flow unchanged; add optional thought persistence only.
2. Summariser: keep summary output/storage flow unchanged; add optional thought persistence only.
3. Image describer: keep description output/storage flow unchanged; add optional thought persistence only.
4. Verify no Telegram streaming path is introduced for non-chatter agents in first rollout.

## Phase 7: Observability and Docs
1. Add structured logs for streaming lifecycle and thought capture writes.
2. Add metrics for stream latency, edit count, fallback count, and thought storage volume.
3. Document privacy and operational guidance for thought capture.
4. Document rollback toggles and failure semantics.

## Dependencies and Parallelism
- Phase 1 blocks Phases 3 and 5.
- Phase 2 can start in parallel with late Phase 1 decisions.
- Phase 3 blocks Phase 4.
- Phase 6 can start once Phase 1 contracts are stable.
- Phase 7 runs throughout and finalizes at rollout.

## Definition of Done
- Chatter supports conversational primary output with optional streaming delivery.
- Tools remain functional for side-effect outputs without replacing conversational text.
- Thought capture and /thoughts retrieval work behind authorization and config gates.
- Classifier, summariser, and image describer retain primary behavior with optional thought logging.
- Test plan matrix passes with no critical regressions.
