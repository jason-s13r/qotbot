# Risks and Mitigations: LLM Conversation Handling and Streaming

## Risk 1: Thought Data Privacy Leakage
- Description: Captured thoughts may contain sensitive or unintended internal reasoning.
- Mitigation: Disabled by default, strict auth on /thoughts, redaction policy, retention TTL.
- Verification: Auth and redaction tests; manual sampling confirms no unintended exposure.

## Risk 2: Streaming Delivery Degrades UX
- Description: Frequent Telegram edits may create noisy or jittery user experience.
- Mitigation: Update throttling, minimum delta size, final clean message commit.
- Verification: UX validation across high/low latency scenarios.

## Risk 3: Telegram Rate Limits and Failures
- Description: Stream-edit cadence may trigger API limits or transient failures.
- Mitigation: Backoff/retry policy, edit frequency cap, fallback to single final send.
- Verification: Integration tests with simulated rate-limit and network failure conditions.

## Risk 4: Conversation/Tool Ordering Regressions
- Description: Tool actions may run before conversational confirmation or duplicate messaging.
- Mitigation: Explicit ordering contract and idempotency checks for side-effect tools.
- Verification: Scenario tests for text-first, tool-first, and mixed flows.

## Risk 5: Agent Contract Drift
- Description: Shared envelope changes may unintentionally alter classifier/summariser/image describer behavior.
- Mitigation: Agent-type compatibility tests and strict defaults preserving existing output paths.
- Verification: Regression suite for approve/reject, summary generation, and image description persistence.

## Risk 6: Storage Growth from Thought Capture
- Description: Persisted thought traces can expand DB size rapidly.
- Mitigation: Per-record size caps, compression/truncation policy, retention cleanup job.
- Verification: Load tests with storage monitoring and cleanup execution checks.

## Risk 7: Ambiguous Source of Truth in Chatter Output
- Description: Final chat-visible response may diverge from logged model output during streaming.
- Mitigation: Persist final delivered message text and stream event checksum for reconciliation.
- Verification: Audit checks confirm delivered text matches final stored response snapshot.

## Rollback Plan
- Disable streaming and thought capture feature flags.
- Revert chatter to single final non-streamed send behavior.
- Keep non-chatter agents on existing non-streamed invocation path.
