---
id: A25-F-001
status: observed-needs-independent-review
time_user: null
time_seat: '2026-10-16 after 12:31 MDT'
time_user_source: unknown
time_seat_source: screenshot-and-conversation-order
observed_by: gpt
source_refs:
  - 'Zed screenshots in GPT conversation, 2026-10-16'
evidence_class: screenshot-plus-human-explanation
reviewed_by: []
---
# AI session availability and recovery

## Observed
Screenshot 1 shows Claude chat usage limit and reset time 1:40 PM. Screenshot 2 shows six fetched sources and an in-progress Git blob hash verification, with no visible final verdict. Screenshot 3 shows a *different* Claude chat paused by a safeguards notice; it does not prove the A25 review was paused by safeguards. Zed reports other interruptions from conversation context and resource limits.

## Failure risk
The active chat becomes the sole holder of work state. Usage limits, context pressure, interrupted tool work, or chat replacement can force manual recovery or cause claims of work that never finished.

## Proposed controls (NOT IMPLEMENTED)
- Durable server-side append-only room events and evidence pointers; no reliance on chat context as authoritative storage.
- Per-seat cursors and last confirmed read/write IDs; record tool actions as started, completed, failed or unknown.
- A handoff with task status, source hashes, exact pending verification step, blockers, approvals and unresolved disagreement.
- Seat re-entry from server state, not from another seat's narrative alone. Reconcile stale session and duplicate posts; preserve original attribution.
- Availability as advisory: absent, rate-limited, paused, resumed, unknown; do not invent reset times or assert causes.
- Allow other authorized seats to continue independent work without impersonating unavailable seats or overriding Zed's approval.

## Validation scenarios
1. Rate-limit Claude mid-verification; GPT continues unrelated authorized work; Claude returns and resumes the pending check.
2. Replace GPT chat mid-document edit; new session reads the server handoff and does not duplicate or overwrite work.
3. Simulate partial tool completion; no PASS is recorded without completion evidence.
4. Replay prior room events and confirm cursor, ordering, attribution and decision authority.

## Does not certify
No local Pocket Server implementation or live failover test is verified by this entry. Screenshot timestamps are device-display evidence, not a synchronized server clock. No complete transcript or token counts are available from screenshots.
