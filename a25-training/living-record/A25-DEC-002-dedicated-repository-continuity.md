---
id: A25-DEC-002
status: approved-direction-pending-new-repository
author: gpt
time_user: "2026-10-16"
time_user_source: conversation-date
claude_review: NOT_REVIEWED
---
# Dedicated A25 repository with permanent pockettest references

## Zed's decision
Keep all existing A25 material in `Stratumnova/pockettest` on `a25/training-workspace`. Do not delete or move it. Establish a new dedicated A25 training and storage repository when authorized and technically available. Once created, update the old A25 reference materials with the new repository's exact URL, authority/cutover boundary, and immutable commit reference so Pocket Server builders can follow the continuity trail.

## Purpose
The original repo remains the Pocket Server software project with its historical A25 training records. The new repo will be the active AI-first training/documentation workspace, not a fork or copy of the server code. Preserve provenance, full content, stable IDs, and independent Claude review status.

## Public/private discussion
Public text repository: GPT can write if connected and authorized; Claude and occasional guest AIs may read public raw links where their platform allows. Private repo: each AI needs authorized credentials or an access broker; a private URL alone does not grant access. Separate sensitive evidence from public training material.

## Pending
- Zed chooses repository visibility and name.
- Create new repository; verify GPT write and Claude read before declaring cutover.
- Copy A25 training materials with hashes and source-commit manifest, without copying Pocket Server code.
- Keep old records unchanged and add forward links only after new repo exists and its URLs are verified.
- No new repository created by this decision record.
