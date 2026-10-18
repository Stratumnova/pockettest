# Zone 1 — GPT connector binding and verification

Status: SOURCE CONTRACT DOCUMENTATION ONLY. Not a live connector installation or phone deployment.
Owner scope: A25-TW-O005 (2026-10-18). Existing source branch: `build/shared-space-v0`.

## Existing source interface
`shared/server.py` calls `make_mcp("gpt")` and `make_mcp("claude")`. Each FastMCP server exposes:
- `workspace_inspect(path: str = ".")`: returns `{path, entries:[{name,type}]}`.
- `workspace_read(path: str)`: returns `{path,content}` for UTF-8 file.
- `workspace_create(path: str, content: str)`: exclusive new file; returns `{ok,path,bytes}`.
- `workspace_edit(path: str, content: str)`: replaces an existing file; returns `{ok,path,bytes}`.
- `workspace_delete(path: str)`: deletes one regular file; returns `{ok,path}`.
- `workspace_command(action: str, path: str = ".")`: action one of `pwd`, `ls`, `python_version`, `pytest`; returns `{action,exit_code,stdout,stderr}`.

All operate under `A25_ZONE1_ROOT` via `shared/zone1_workspace.py`. The same root is configured for both MCP routes. Relative paths are required; inspect/command allow `.` as working directory. Content limited to 1,000,000 UTF-8 bytes; command timeout 30 seconds. This is local-trust prototype code, not a claim of hardened isolation.

## Connector setup required after separate owner deployment approval
1. G1 supplies tested source SHA, source install procedure, environment variables, and actual existing Android bridge route details without sharing route secrets in GitHub.
2. On the phone, after owner authorization, deploy/update **the existing** Pocket MCP process and configure `A25_ZONE1_ROOT` to the desired same local working directory. Confirm both existing GPT and Claude MCP route mounts point to the same process/root. Do not assume source commit means deployment.
3. In GPT ChatGPT plugin/connector configuration, connect to the existing GPT-specific Pocket MCP HTTPS endpoint (actual tunnel and secret route held privately by owner). Refresh/discover tools. The separate A25 GPT Terminal plugin's `terminal_view` and `terminal_status` are NOT substitutes and cannot send shell commands.
4. Confirm GPT tool discovery explicitly advertises all six `workspace_*` names; record exact names and responses. If discovery lacks them, STOP and diagnose plugin/server version or exposure rather than claiming success.
5. Claude activation/connector installation is separate and later. No secrets should be posted to GitHub.

## Acceptance procedure (execute ONLY after separate live authorization)
- GPT: `workspace_inspect(".")`; create `zone1-acceptance-gpt/hello.py` containing a simple deterministic function and `zone1-acceptance-gpt/test_hello.py` testing it. Note: `workspace_create` creates parents in current source.
- GPT: `workspace_read("zone1-acceptance-gpt/hello.py")`; `workspace_command("pytest","zone1-acceptance-gpt")`; record actual exit code, stdout and stderr.
- Claude, once separately activated: read the same file; edit it to implement a jointly agreed changed behavior; record response and file bytes. This tests shared physical workspace, not courier.
- GPT: read Claude's updated file; edit the test accordingly if needed; rerun `workspace_command("pytest","zone1-acceptance-gpt")`; record output and distinguish genuine success from expected failure.
- GPT: create and delete a disposable `zone1-acceptance-gpt/delete-me.txt`, verify it disappears with inspect. Do not delete project files.
- Preserve a source SHA, actual connector tool list, timestamps, phone output and failures. Do not claim cross-seat success before it happens.

## Limitations and diagnostics
- Current GPT session's A25 GPT Terminal plugin exposes only `terminal_status` and `terminal_view`; six workspace operations are **not yet exposed through that plugin**.
- `workspace_edit` replaces entire text; it is not a patch operation. No revision preconditions or conflict prevention: serialize simultaneous edits.
- `workspace_command` is bounded to four action IDs, not an arbitrary shell. `pytest` executes code under the local trust model.
- `Workspace` creates the configured root during initialization; this must be an explicitly chosen location at deployment.
- GitHub repository tools modify remote GitHub files, not the Android workspace.
- The source was inspected remotely; no phone deployment, live shell, or cross-AI acceptance tests were performed under O005.
