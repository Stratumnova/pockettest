# Pocket Server / Roundtable — recovery index

Checkpoint date: 2026-10-08. This directory is intended to preserve the project across lost ChatGPT/Claude sessions.

## Checkpoint PDFs (to archive here)

- `Gate02_Checkpoint_GPT_2026-10-08.pdf` — infrastructure, DNS, tunnel, tests, architecture, and roadmap.
- `Gate02_Checkpoint_Claude_2026-10-08.pdf` — debugging history, runtime lessons, Termux runbook, and Roundtable index.

**Note:** The two PDFs are not committed by this index commit; do not mistake the index for an archived copy. Keep the downloaded PDFs until both binary files are uploaded and verified in this folder.

## Confirmed checkpoint

- Gate-01 is GREEN and FROZEN. Do not modify `gate01/` without explicit owner approval.
- Local phone directory: `~/pockettest/gate01/`; ledger `roundtable.jsonl` and backup `roundtable.backup.jsonl`, last verified with 3 events each.
- Gate-01 exchange: Claude event 1, GPT event 2, Claude event 3. Server-side identity, unseen/context cursors, restart persistence and client recovery verified.
- Repository: `Stratumnova/pockettest`; Gate-01 server checkpoint commit `b539bd8ef2282cedf0b57c2d1d84c50b6fecd941`.
- Gate-02 domain: `rodsrcpark.com`, Cloudflare-managed DNS; hostname `roundtable.rodsrcpark.com`.
- Named tunnel `pocket-server-gate02`, ID `1f916171-f2d0-43e2-9eb2-66ae75de3d1f`, successfully connected from Termux `cloudflared 2026.10.0` on Android ARM64.
- Published route: `roundtable.rodsrcpark.com` -> `http://127.0.0.1:8765`; DNS CNAME created. Browser returned expected 502 while origin server was stopped. Successful public request to a running Gate-02 server **not yet tested**.
- Gate-02 is not implemented; no private project files are approved for exposure. Old Gate-01 secret paths were disclosed in testing and must not be reused.
- Gate-02 development should use a separate app and port (proposed 8766), keeping the existing public route off Gate-01. Update the route only for controlled Gate-02 tests.
- Authentication proposal (Roundtable #0028): inspect MCP SDK 1.26.0 OAuth support; test OAuth + PKCE + dynamic client registration compatibility with both Claude and ChatGPT; settle platform attribution (redirect URI alone is insufficient proof), owner consent, token hashing/revocation, and authorization tests.
- Next **read-only** Termux command: `cd ~/pockettest/gate01 && source .venv/bin/activate && python -c "import importlib.metadata; print('MCP SDK:', importlib.metadata.version('mcp'))"`

## Security and recovery

- Never commit tunnel tokens, OAuth credentials, secret paths, personal project data, or raw private ledger entries to this public repository.
- Keep Gate-01 local ledger and backup intact. Do not treat GitHub code commits as backups of phone-local data.
- Run one command at a time and verify each result before proceeding.
- Future plans: authenticated Roundtable, approved read-only project access, separate human/AI identities, multi-user rooms, and Android start/stop controls.
