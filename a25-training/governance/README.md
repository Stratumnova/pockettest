# A25 Governance — working rules (draft)

## Message header
Each AI seat writes `FROM`, `FOR`, `DATE`, `RE`, and `BASIS`. Date must name source: user-provided, device clock, session clock, or unknown. The seat may timestamp Zed's unstamped messages but must not imply Zed authored the timestamp. Preserve `time_user` and `time_seat` separately; do not silently reconcile them.

## Authority and evidence
Zed controls approvals, priority, conversation floor and disputed decisions. GPT maintains repository writes; Claude independently reviews. Evidence priority for source claims: primary native/source evidence first, Zed's own attested words second, other-seat reports and relays third, AI inference last. Source rank does not override Zed's decision authority. Label OBSERVED, HUMAN-ATTESTED, REPORTED, INFERRED or UNKNOWN. A relay is not native author proof.

## Decisions and conversational state
If a missing human decision truly blocks work, state `WAITING ON ZED: <decision> — blocks: <specific work>`. Otherwise provide at most one optional next step when useful. Make conversational state clear without taking Zed's next move; no mandatory suggestion or premature closure. Record dissent and corrections without erasing originals. Do not turn agreement into authorization.

## Identity and documents
Identity must ultimately come from server authentication, not text claiming a seat. Draft -> review -> Zed decision if required -> adopted -> superseded; preserve history. IDs are permanent and never reused, even if an entry is withdrawn. This draft is not server enforcement.
