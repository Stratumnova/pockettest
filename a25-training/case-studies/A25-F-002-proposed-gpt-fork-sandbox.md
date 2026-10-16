---
id: A25-F-002
type: proposed-workspace-safety-experiment
status: proposed-not-implemented
time_user: "2026-10-16 13:07 MDT"
time_user_source: "Zed's message"
time_seat: null
time_seat_source: unknown
author: gpt
reviewed_by_claude: false
source_refs:
  - "Zed's GitHub branches screenshot supplied in GPT chat on 2026-10-16"
evidence_class: "user-supplied-screenshot-and-proposal"
---
# GPT fork sandbox with protected original — proposal

## Why this came up
Zed wants GitHub to be the AI-first full-fidelity working portfolio rather than a site Zed must manually operate. Manual copy/paste between GPT and Claude can lose information. Claude's availability is limited, while GPT needs room to develop and archive training material. Zed is exploring a protected original and a high-autonomy GPT working copy, followed by selective return after Claude re-enters.

## Screenshot observations
The screenshot of GitHub's Stratumnova/pockettest branches page, shown at approximately 1:05 on Zed's device, displays default branch `main` and branches `a25/training-workspace`, `proposal/shared-space-stage-2-...` (truncated on screen), `build/shared-space-v0`, and `build/gate02a-c1-auth-store`. The displayed A25 branch is 21 commits ahead of main at screenshot time. Screenshot alone does not establish a fork, permissions, branch protections, or present-day branch status.

## Zed's proposal, 1:07 PM MDT
Zed proposes forking the project, giving GPT full use and permissions in the fork, possibly retaining the fork as GPT's own repository/tool if successful, while preserving the original with limited write access for its health. When Claude returns, Zed, GPT, and Claude discuss which tested changes should return to the original. Zed explicitly says he does not fully understand GitHub forking yet.

## Technical distinctions
A GitHub fork is a distinct repository with a parent relationship, not a continuously synchronized mirror. Changes do not automatically flow upstream. Branching is different: the current `a25/training-workspace` is a branch inside the original repository, not a fork. The screenshot shows branches, not forks. GPT's actual effective privileges depend on connected GitHub credentials, repository ownership, and GitHub permissions; user authorization in chat alone does not grant 100% technical access.

## Proposed boundaries and test
1. Confirm fork owner, visibility, branch to fork from, and connected tool capabilities before creation.
2. Keep the original repository unchanged except explicitly approved documentation until the fork experiment is accepted.
3. Give GPT broad experimental write scope only in the fork, while retaining safeguards for secrets, destructive changes, and external effects.
4. Preserve original commit provenance, independent Claude review status, test evidence, and a manifest of proposed upstream changes.
5. When Claude returns, review changes individually; Zed decides whether to merge, cherry-pick, or reject them.
6. Test actual access and ability to recover from a new GPT session. Do not equate a written policy with enforced permissions.

## Status and unresolved decisions
Proposal recorded; no fork created; no GitHub access permissions changed; no upstream merge approved. Determine whether the fork should copy `main` only or also include the A25 training branch, which owner account should hold it, and whether the connector supports fork creation. Claude review pending.
