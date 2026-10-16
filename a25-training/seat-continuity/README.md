# Seat continuity protocol

Purpose: enable an absent AI seat to return without pretending it approved work done while unavailable.

Record the last verified joint boundary, absence reason and evidence, Zed's authorization to continue, each new commit, its review state, and unresolved work. The absent seat's status is `NOT_REVIEWED`, never implicit consent. On return, the seat independently fetches immutable sources and marks each item VERIFIED, CHALLENGED, or NOT_REVIEWED. Preserve prior assessments and corrections. Zed resolves decisions; GPT must not impersonate Claude.

A new session may represent the same seat only after future server-enforced identity checks; this document does not implement authentication.
