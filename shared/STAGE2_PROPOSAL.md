# Shared Space Stage 2 — Identity proposal

**Base:** `9a419e925dff2de64ef948b7d6d8304eccf8387d`

**Status:** proposal only; no merge, deployment, credential generation, or
modification of frozen Gate-01/Gate-02A services.

## Scope

- Add an isolated, testable identity configuration module.
- Recognize only `gpt` and `claude` as remote actors.
- Require distinct, URL-safe 32–128-character random path segments supplied
  at runtime as `A25_SHARED_GPT_PATH` and `A25_SHARED_CLAUDE_PATH`.
- Reject missing, duplicate, malformed, and placeholder credentials.
- Reserve `owner` for locally authorized CLI operations; there is no remote
  owner identity or owner MCP endpoint.
- No terminal execution, Git writes, file edits, or remote owner commands.

## Important limitations

Secret paths are bearer credentials, not OAuth or proof of the actual
provider's identity. Anyone who obtains a path can act as that actor.
Transport TLS, careful connector configuration, secret redaction, and
rotation are required before exposure. This module alone does not enforce
network authentication, rate limits, revocation, or remote permissions.

The existing Stage 1 `shared/server.py` reads legacy secret paths at
module import time; storage paths are initialized during lifespan startup.
It also has existing dummy-data MCP tools. **It is deliberately
unchanged in this proposal.** Integration of this identity module into
server startup, local owner administration, and complete permission tests
must be reviewed and approved as a separate Stage 2 integration step
before any service is launched. Do not deploy this proposal as-is.

## Proposed local verification

```sh
cd ~/pockettest-shared/shared && ~/pockettest/gate02/.venv/bin/python -m pytest -q
```

The owner should verify the pinned commit and full file hashes on the
phone. Claude should independently review the exact commit before
integration, merge, or deployment.

## Independent review fixes

- Removed the misleading loopback-based owner-authority helper. Owner
  administration must be implemented only as a separate local CLI, with no
  HTTP owner route or caller-provided owner identity.
- Non-ASCII request paths now fail closed instead of raising TypeError.
- New environment names deliberately do not read legacy Gate-01 secrets.
- Server integration must replace, not duplicate, its existing validator.
