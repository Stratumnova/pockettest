# Current State

## Objective
Create a small personal server whose authoritative workspace lives on the user's Android phone and can serve selected project files to GPT and Claude.

## Security model
- Project area: owner write; GPT/Claude read-only.
- Roundtable: owner read/write; GPT/Claude read + append only.
- Separate credentials for GPT and Claude.
- Credentials are revocable independently.
- Server enforces identity and capability; the client does not choose its own author name.
- No AI delete capability in V1.
- No arbitrary filesystem access.
- No shell or arbitrary command execution.
- All AI-facing paths must remain under the configured Pocket Server root.

## Development staging
GitHub repository `Stratumnova/pockettest` is the experimental development workspace.
GPT has broad permission to modify this repository.
Claude may be able to read it but currently may not be able to write to GitHub.

## Design principle
Pocket Server is not an AI client and does not call model APIs. It is a controlled shared storage/conversation doorway.
