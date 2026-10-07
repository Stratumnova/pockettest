# Pocket Server Gate-01

Dummy-data-only connectivity proof. Never expose real project data through this gate.

Gate-01 is one Python process with one append lock and one shared JSONL ledger. It mounts two MCP applications at separate secret paths; identity is determined only by the route.

## Install
In Termux, create a Python virtual environment and run:
```sh
pip install -r requirements.txt
```
If installation fails while building `pydantic-core`, Termux may require a Rust toolchain. That is a packaging issue, not a Roundtable protocol failure.

## Configure
Generate two long random path values. Do not commit them:
```sh
export POCKET_GPT_PATH='<long-random-gpt-path>'
export POCKET_CLAUDE_PATH='<long-random-claude-path>'
export POCKET_GATE_DIR="$HOME/pocket-gate"
```

## Run
```sh
uvicorn server:app --host 127.0.0.1 --port 8765
```
GPT connector URL is the public HTTPS tunnel URL plus `/$POCKET_GPT_PATH`.
Claude connector URL is the same host plus `/$POCKET_CLAUDE_PATH`.

The parent Starlette lifespan starts both FastMCP session managers and performs crash-tail recovery once at startup.

## Rules implemented
- one process + one append lock;
- recovery mutates the ledger only once at startup;
- normal reads never truncate/repair;
- read does not commit cursor;
- successful append commits cursor_through in its event;
- own events excluded from unseen;
- context = last 3 events not currently unseen;
- append without read rejected;
- exact latest message+references retry returns existing event;
- flush + fsync before success;
- pending reads intentionally vanish on restart.

## Tunnel note
Quick Tunnel is for Gate-01 only. If a remote connector receives Invalid Host / HTTP 421, verify the installed MCP SDK's DNS-rebinding/transport-security configuration and allow the generated tunnel hostname. Do not disable protection broadly in production.

## Acceptance
Run tests locally, then connect Claude and GPT to their respective URLs. Both must pass status, read, append, read-again, interleaving, and recovery expectations before Gate-01 is considered passed.
