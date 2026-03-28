# Epic: Owner-Only LLM Tools

## Overview
Add owner-scoped tool availability to the response pipeline so personal/admin tools are only available when the triggering sender is the configured bot owner. Preserve current behavior for non-owner users and keep public tool packs unchanged.

## Goals
- Enforce owner-only tool exposure at runtime per message.
- Support personal tools (for example ordering/household workflows) without leaking capability to other users.
- Add defense-in-depth checks inside sensitive tool handlers.
- Keep non-owner experience unchanged.

## Non-Goals
- Reworking command permission architecture.
- Redesigning classifier behavior.
- Building production-grade ordering/payment integrations in this epic.

## Architecture Direction
- Authorization source: `TELEGRAM_BOT_OWNER` from config.
- Decision point: response tool assembly in response worker, once per message.
- Pattern: dedicated owner provider/tool pack mounted conditionally.
- Hardening: handler-level owner assertions for side-effect tools.

## Acceptance Criteria
- Owner-only tools are available only for owner-triggered messages.
- Owner-only tools are absent for non-owner-triggered messages.
- Existing public tools still function for all users.
- On sender lookup failure, owner tools are not mounted.
- Owner-only handlers reject execution when authorization context is false.

## Deliverables
- Runtime gating in response path.
- Owner tools provider/module scaffold.
- Safety controls (limits/logging) for sensitive actions.
- Documentation updates for setup and operational behavior.

## Dependencies
- Reliable `sender_id` retrieval for the message being processed.
- `TELEGRAM_BOT_OWNER` configured in environment.

## Rollout Notes
- Start with no-op or read-only owner tools first.
- Add external side-effect tools behind explicit confirmation flags.
- Monitor logs for authorization decisions and blocked attempts.
