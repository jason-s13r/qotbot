# Tasks: Owner-Only LLM Tools

## Phase 1: Authorization Plumbing
1. Resolve triggering sender from message record in response processing.
2. Compute `is_owner` using `TELEGRAM_BOT_OWNER`.
3. Implement fail-closed behavior when sender lookup fails.
4. Add structured log event for authorization decision.

## Phase 2: Conditional Tool Exposure
1. Keep baseline public tool mounts unchanged.
2. Add conditional mount for owner-only tool pack when `is_owner=true`.
3. Ensure no conditional leakage through transforms or schema generation.

## Phase 3: Owner Provider and Security
1. Create dedicated owner provider/module for private tools.
2. Bind trusted caller context at provider initialization.
3. Add handler-level owner checks (defense in depth).
4. Avoid model-supplied identity parameters for auth-critical decisions.

## Phase 4: Safety and Controls
1. Add per-tool call limits for risky owner actions.
2. Define dry-run defaults for tools with external side effects.
3. Add minimal audit logs for owner tool usage (without secrets).

## Phase 5: Documentation
1. Document owner-only behavior in project docs.
2. Clarify env requirements and failure semantics.
3. Add guidance for adding future personal tools safely.

## Dependencies and Parallelism
- Phase 1 blocks Phase 2.
- Phase 3 can start after Phase 1 and run in parallel with parts of Phase 2.
- Phase 4 depends on Phase 2 and Phase 3.
- Phase 5 can run in parallel with late Phase 3 and Phase 4.

## Definition of Done
- All acceptance criteria in epic README are satisfied.
- Verification matrix passes for owner, non-owner, and failure paths.
- No regressions in public tool availability.
