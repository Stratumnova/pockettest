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


## Connector gate findings (Claude research)
- Common remote-MCP auth intersection reported: OAuth or no authentication.
- Static bearer-token headers must not be assumed.
- Gate test should use dummy data only and temporary no-auth exposure.
- Production target is OAuth with caller identity/authorization derived server-side.
- Remote MCP endpoint must be publicly reachable over HTTPS; local-only phone addresses are insufficient.
- Critical unknown: verify whether the user's current ChatGPT plan permits the Roundtable append/write tool. Treat this as a gate, not an assumption.
- Claude custom-connector reachability and ChatGPT tool-write capability must be proven before building the full Android server.
