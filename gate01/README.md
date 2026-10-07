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
The FastMCP app keeps its default internal `/mcp` path. Therefore the connector URLs are:
```
https://<tunnel-host>/$POCKET_GPT_PATH/mcp
https://<tunnel-host>/$POCKET_CLAUDE_PATH/mcp
```
The server refuses to start if either secret path is missing, shorter than 24 characters, still contains `CHANGE-ME`, or the two paths are equal.

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
Quick Tunnel is for Gate-01 only. Gate-01 will keep DNS-rebinding protection enabled. Start cloudflared, note the generated tunnel hostname, then configure the MCP SDK transport-security allowed-hosts for that exact hostname and restart the local server if the installed SDK rejects the tunnel Host header. Do not disable protection broadly.

## Acceptance
Run tests locally, then connect Claude and GPT to their respective URLs. Both must pass status, read, append, read-again, interleaving, and recovery expectations before Gate-01 is considered passed.
