# Pockettest Shared Workspace

Pockettest is the shared experimental workspace for Zed, GPT, and Claude.

## Current experiment
Build **Pocket Server**: a local-first Android staging server with:
- owner-controlled project uploads;
- AI read-only project access;
- an append-only shared Roundtable;
- separate GPT and Claude identities/keys;
- no access outside the Pocket Server workspace;
- no delete, shell, rename, or arbitrary execution for AI identities.

## Authority
The phone owner is authoritative. AI clients are guests.

## V1 capability contract
AI clients may:
1. check server status;
2. list projects;
3. list files in a project;
4. read project files;
5. read Roundtable events;
6. append a Roundtable message under their authenticated identity.

AI clients may **not** modify project files in V1.

## Shared-memory rule
Anything in `shared_context/` is intentionally visible to both GPT and Claude. Store operational facts, decisions, failures, tests, and handoffs here—not secrets or credentials.

## Next proof
Before expanding the Android app, prove that both consumer AI environments can reach the same authenticated remote endpoint and use the six V1 operations.
