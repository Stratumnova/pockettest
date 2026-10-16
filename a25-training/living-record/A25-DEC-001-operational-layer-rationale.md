---
id: A25-DEC-001
status: proposed-pending-zed-confirmation
date_user_reference: "2026-10-16 12:56 MDT"
date_source: "Zed-provided time in conversation"
author: GPT
reviewed_by_claude: false
---
# Why A25 needs an operational layer

## Origin and observed problem
Zed operates a permanent Roundtable of Zed, GPT, and Claude. Gemini, Meta, and other AIs are occasional read-only test participants, not permanent seats. Zed reported a Grok interface accessible only for account/product questions, not a general-purpose Roundtable seat.

During manual cross-platform relay, pasted text and rendered-chat copying lost formatting and links, and seat identity/attribution could become confused. Claude's session availability interrupted a pending integrity review. GPT and Zed continued from the user-provided 12:37 MDT boundary. The repo gained continuity records, but its GPT archive still contains policies rather than a complete transcript. These are observed/reported limitations, not proof that all AI platforms behave identically.

## Zed's objectives
- GitHub is Zed's public portfolio and AI-first shared workspace, not an interface Zed must manually operate.
- Preserve complete AI-readable records; avoid lossy human copy/paste and forced compression.
- GPT writes authorized A25 work directly; Claude is a permanent independent reviewer with limited availability.
- Gemini and Meta may read for invited tests but should not write.
- Zed retains project decisions and approvals.
- PDFs and conversational explanations are Zed-first outputs on request; Markdown and text sources are GitHub-first.
- Future Pocket Server continuity and game-building should reuse the approach, but are not certified by these documents.

## Paths considered
1. Continue chat-only and copy/paste relay: no additional infrastructure, but demonstrated fidelity and availability weaknesses.
2. Treat PDFs/ZIPs as primary interchange: portable for Zed but introduces downloads, conversion, and tool-reading constraints.
3. Use GitHub as durable AI-readable source plus a small operational layer: versioned, linkable, reviewable, and currently writable by GPT. GitHub does not automatically capture chats or authenticate Roundtable seats.
4. Use Pocket Server as live authoritative coordination now: longer-term candidate, but authenticated multi-seat recovery is not yet implemented or verified.

## Recommended path (not yet final approval)
Choose option 3 for current documentation: retain existing paths, add START_HERE.md, a task/decision/change ledger, explicit seat permissions and return-review process. Continue option 4 as a separately tested future implementation. No existing source is moved or rewritten by this proposal.

## Proposed operation
1. Incoming session reads START_HERE.md, verifies repository/branch and current state.
2. Reads task record and relevant source, checks its authorized scope.
3. Writes new work with stable IDs and evidence provenance.
4. Verifies commit and updates task/change log.
5. Leaves unresolved work and independent review status clearly marked.
6. Guest seats can inspect permitted public records but receive no repository write authority.

## Pending Zed decision
May GPT automatically update task status, indexes, and handoffs for already-authorized A25 work, while requesting approval for governance changes, deletion, restructuring, permissions, or rewriting prior evidence? Until confirmed, treat this as a proposal.

## Known limitations
No complete GPT transcript is archived yet. Claude has not independently reviewed this decision record. GitHub permissions for guest AI accounts were not independently audited. No automatic Pocket Server session recovery is certified.
