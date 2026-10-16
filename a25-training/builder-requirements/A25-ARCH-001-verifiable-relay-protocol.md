---
id: A25-ARCH-001
status: design-proposal-not-implemented
author: gpt
date: "2026-10-16"
reviewed_by_claude: false
authority: "Zed authorized a public dedicated A25 repository and GPT trusted-relay experiment"
---
# A25 Archivist: verifiable relay and archive protocol

## Context and intent
Zed, GPT and Claude are the permanent Roundtable. Other AIs (including Gemini and Meta) participate only in explicitly invited tests and should have read-only access. A reported Grok product-scoped session is not a permanent seat. Zed wants AI-first full-fidelity records in a dedicated public training repository, without copying Pocket Server code. PDFs and explanations are Zed-first outputs on request.

Zed authorizes testing GPT as a trusted relay while developing an Archivist to assume this role. Transport authority does not grant source authorship, seat impersonation, independent reviewer status, or approval of Zed's decisions.

## Record contract (proposed)
Every archived item has:
- `record_id` (stable, never reused)
- `source_seat` and `captured_by` (separate)
- `source_kind` (native export, direct message, screenshot, user relay, reconstruction, derived)
- `source_time`, `capture_time`, `time_sources`, and `timezone` (unknown allowed)
- `coverage` and `known_omissions`
- `content_path`, `sha256_utf8`, `byte_count`
- `github_commit`, `github_blob_sha`, `pinned_raw_url`
- `verification_state`, `verified_by`, `review_state`, `reviewed_by`
- `supersedes` and `correction_of` when applicable
- `authority_scope` and `decision_status`

## Verification ladder
1. CAPTURED: source obtained, provenance and omissions labeled.
2. COMMITTED: GitHub accepted a write; commit SHA returned.
3. READ_BACK_MATCH: fetch the exact committed file at its immutable commit and compute SHA-256 of returned UTF-8 bytes, matching precommit hash. This proves archive write/read parity, not source truth.
4. INDEPENDENTLY_CHECKED: a separate seat verifies the pinned content against its own source or independently available evidence. Name the seat and scope of comparison.
5. APPROVED: only when Zed explicitly approves a decision; transport or review never implies this state.

A failed hash, incomplete capture, ambiguous source, or unavailable read-back must produce a visible failure or UNVERIFIED state, never a silent PASS.

## Paths in new dedicated repository (proposed)
- `START_HERE.md`: recovery entry point
- `A25_gpt_transcripts/`: GPT-authored archives and artifacts
- `records/raw/`: immutable source-preserving records
- `records/manifests/`: machine-readable provenance and hashes
- `records/corrections/`: append-only correction references
- `living-record/`: tasks, current state, decisions, and handoffs
- `reviews/claude/`: independently authored or faithfully attributed Claude findings
- `reviews/guest/`: read-only guest test results with explicit source provenance
- `validation/`: parity and recovery tests

## Roundtrip experiment
- Capture one deliberately small, non-sensitive source message with known punctuation, markdown, Unicode, links, and attribution.
- Record exact source bytes if available; otherwise clearly identify the reconstructed or copied source boundary.
- Compute SHA-256 locally; commit source plus manifest.
- Fetch the file by commit SHA; compare byte count and SHA-256.
- Give Claude a single pinned raw URL and ask for independent comparison with its own original.
- Return the pinned link and status to Zed, with no required download/re-upload.
- Deliberately introduce a changed character in a second test; require mismatch detection.
- Add correction as a new record and verify both original and correction remain discoverable.
- Test new-session recovery without prior chat access.

## Current limits
GitHub connector exposes file and branch operations but no repository-creation operation in this session. New public repository has not been created. No relay parity test or automated Archivist has yet passed. Private/secret evidence must not be committed to public GitHub. GitHub public read does not guarantee every AI platform can fetch a link.

## Continuity
Keep existing `Stratumnova/pockettest` A25 branch intact. Once the new repository exists and has been verified, add a forward link and migration manifest to the original, without deleting historical files. Claude reviews before any claims of cross-seat parity.
