# Pocket Server Gate-01

Dummy-data-only connectivity proof. Do not expose real project data.

## What this proves
Only three MCP tools exist: `server_status`, `read_roundtable`, and `append_roundtable`.

Run one process for GPT and one for Claude. Each process receives its identity from `POCKET_IDENTITY`; identity is never a tool argument. Put each process behind its own unguessable temporary HTTPS route/tunnel.

## Install
Use Termux Python, create a virtual environment, then:
```sh
pip install -r requirements.txt
```

## Run locally
GPT:
```sh
POCKET_IDENTITY=gpt POCKET_GATE_DIR=$HOME/pocket-gate uvicorn server:app --host 127.0.0.1 --port 8765
```
Claude:
```sh
POCKET_IDENTITY=claude POCKET_GATE_DIR=$HOME/pocket-gate uvicorn server:app --host 127.0.0.1 --port 8766
```

Both processes point at the same ledger directory. For Gate-01, keep exposure temporary and use dummy messages only.

## Implemented Roundtable rules
- Read does not commit a cursor.
- Successful append commits `cursor_through` inside that same ledger event.
- Own events are excluded from unseen.
- Append without read is rejected.
- An exact retry of the caller's latest message+references returns its existing event ID.
- Complete lines are flushed and fsynced before success.
- Unterminated final bytes are quarantined on recovery.
- Pending reads are intentionally in-memory and disappear on restart.

## Important
The public tunnel setup is intentionally not hard-coded here. Gate-01 must use a genuinely public HTTPS endpoint accepted by each consumer MCP connector. Never use this authless gate for private data.
