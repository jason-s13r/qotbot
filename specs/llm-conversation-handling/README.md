# Epic: LLM Conversation Handling and Streaming

## Overview
Redesign the LLM interaction model so the primary assistant reply is treated as a conversational response, with tools used for supplemental side effects. Add optional thought capture, model response streaming, and Telegram progressive delivery.

This epic introduces a clearer split between:
- conversational response text (the assistant speaking in chat), and
- tool output artifacts (polls, files, actions, admin effects).

## Goals
- Support optional capture of model reasoning/thought text for inspection via a dedicated retrieval command.
- Support streamed model responses from the LLM backend.
- Support streamed Telegram delivery for conversational replies (chunked send and/or message edits).
- Make the default response shape one conversational reply message, with tools as additional capabilities.
- Keep tool actions available for non-text outputs (for example poll/file/action workflows).
- Define expected behavior across chatter, classifier, summariser, and image describer.

## Non-Goals
- Replacing the existing command framework.
- Rewriting all tool providers.
- Storing thought data by default for all chats without explicit enablement.
- Introducing chain-of-thought exposure to users by default.

## Architecture Direction
- Introduce a conversation result envelope from LLM invocations:
  - final_text: primary assistant response text.
  - tool_actions: executed tool calls and outputs.
  - thoughts: optional captured reasoning artifacts.
  - stream_events: optional sequence of text delta events.
- Add feature flags/config for:
  - thought capture enablement,
  - model streaming enablement,
  - Telegram progressive delivery enablement.
- Persist thoughts only when enabled, linked to chat_id/message_id/run_id with retention controls.
- Add a /thoughts command for owner-authorized retrieval of thought records.
- Update the chatter prompt contract so conversational text is expected as primary output, not only tool calls.

## Agent-Type Effects

### Chatter (interactive responses)
- Primary mode: generate conversational text as final_text.
- Tools remain available for side effects and non-text outputs.
- Delivery path:
  1. stream model deltas when enabled,
  2. progressively send/edit one visible Telegram response message,
  3. execute additional tool outputs as separate messages/artifacts only when needed.
- Fallback: if streaming unavailable, send final non-streamed text.

### Classifier (approve/reject)
- No Telegram streaming output needed.
- Keep tool-based decision API (approve/reject) intact.
- Optional thought capture can record rationale for diagnostics when enabled.
- Ensure classifier thought capture never leaks into chat-visible responses.

### Summariser (summary generation)
- No Telegram token streaming requirement for first phase.
- Maintain current behavior of producing final summary text and posting summary/file outputs.
- Optional thought capture may store internal reasoning metadata for debugging quality regressions.
- Ensure stored summary output remains authoritative; thoughts are auxiliary.

### Image Describer (vision annotation)
- No Telegram streaming output needed.
- Continue producing a concise final description for DB storage.
- Optional thought capture may store reasoning traces for difficult images when enabled.
- Preserve current latency-sensitive path and avoid excessive storage growth.

## Acceptance Criteria
- Chatter can return and deliver a conversational final_text without requiring send_message tool usage.
- Chatter supports model streaming and Telegram progressive message updates behind config flags.
- Chatter can still execute additional tools for side effects in the same run.
- Thought capture can be enabled/disabled globally (and optionally per agent type).
- /thoughts retrieves persisted thought records with authorization and filtering controls.
- Classifier, summariser, and image describer continue to function without behavior regressions when thought capture is disabled.
- Classifier, summariser, and image describer can optionally persist thought traces when enabled, without affecting their primary outputs.
- On streaming failure, response path degrades gracefully to non-streamed final delivery.

## Deliverables
- Spec and schema for conversation result envelope.
- DB schema updates for thought records and retention metadata.
- New /thoughts command behavior and authorization rules.
- Streaming adapter for LLM delta events.
- Telegram progressive delivery adapter (chunked send/edit updates).
- Updated prompts/contracts for chatter and compatibility notes for other agents.
- Operational documentation for toggles, privacy, and debugging usage.

## Dependencies
- LLM provider support for streamed completions/events.
- Telegram client support for message edits and rate-limit-safe update cadence.
- DB migration path for thought persistence.
- Existing auth controls for owner/admin-only command access.

## Rollout Notes
- Ship behind feature flags with streaming and thought capture off by default.
- Roll out chatter streaming first, then optional thought capture for non-chatter agents.
- Validate rate limits and message quality before enabling progressive delivery broadly.
- Include a fast rollback path to current non-streamed final-send behavior.
