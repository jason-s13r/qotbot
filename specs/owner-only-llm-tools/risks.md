# Risks and Mitigations: Owner-Only LLM Tools

## Risk 1: Capability Leakage to Non-Owner
- Description: Owner tools accidentally appear in schema for non-owner messages.
- Mitigation: Mount owner pack only after explicit `is_owner` check; default deny on errors.
- Verification: Non-owner integration test asserts owner tool absence.

## Risk 2: Auth Bypass via Tool Arguments
- Description: Model passes forged user identifiers into tools.
- Mitigation: Do not trust model-supplied identity for authorization; use trusted context bound at provider init.
- Verification: Negative test with forged parameters still fails.

## Risk 3: External Side Effects (Ordering/Purchases)
- Description: Unintended transactions or repeated actions.
- Mitigation: Dry-run by default, explicit confirm params, per-tool call limits, idempotency keys when possible.
- Verification: Repeated invocation attempts are blocked or deduplicated.

## Risk 4: Operational Misconfiguration
- Description: `TELEGRAM_BOT_OWNER` missing or incorrect.
- Mitigation: Startup validation and clear log warning; fail closed for owner tools.
- Verification: Misconfigured env disables owner tools and does not expose them.

## Risk 5: Audit Gaps
- Description: Hard to trace who triggered sensitive actions.
- Mitigation: Structured logs for auth decisions and owner-tool invocations with redaction.
- Verification: Log sampling confirms required fields and no secret leakage.

## Risk 6: Regression in Existing Public Tools
- Description: Tool assembly changes break normal responses.
- Mitigation: Keep baseline mounts untouched and add regression tests for public tools.
- Verification: Public tool scenarios pass for non-owner messages.

## Rollback Plan
- Disable owner tool mounting via feature flag or config toggle.
- Keep public tool path unchanged so normal response flow continues.
