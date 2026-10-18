# A25 Zone 1 — Separate GPT Actions connection

This is a **second ChatGPT connector entry**, not a replacement for the A25 GPT Terminal plugin. The original read-only `terminal_status` / `terminal_view` remain untouched. The separate Actions entry uses the **existing** Pocket Server GPT MCP endpoint and its existing workspace registrations; it does not require a new service, new route, or new credentials.

## Source registration and machine-readable entry
`shared/server.py` currently creates `GPT=make_mcp("gpt")` and registers `workspace_inspect`, `workspace_read`, `workspace_create`, `workspace_edit`, `workspace_delete`, `workspace_command`. `shared/zone1_workspace.py` provides the implementation. `shared/zone1_actions_entry.json` records the second connector's intended tool surface and connection model. This JSON is **setup metadata**, not a ChatGPT plugin installation and not a promise that ChatGPT imports this JSON automatically.

## Owner-side installation after separate live approval
1. Preserve the existing A25 GPT Terminal plugin/connector configuration unchanged.
2. G1/owner checks source tests in the existing Termux checkout and deploys the existing Pocket Server update only under a separate live order. Confirm `A25_ZONE1_ROOT` in the running server's environment and verify the current GPT MCP endpoint is reachable; do not publish the secret path.
3. In ChatGPT's Plugins/Connectors management, create a **separate** MCP connection called **A25 Zone 1 Actions** pointing to the owner's current Pocket Server **GPT** Streamable HTTP HTTPS URL (tunnel base + existing private GPT route). Use the supported ChatGPT MCP connector configuration for that account. Do not edit or replace the A25 GPT Terminal entry. If ChatGPT cannot add a second MCP connection to the same endpoint, report the UI limitation; do not create a second server or guess another URL.
4. Inspect tool discovery for all six workspace tools. `workspace_inspect` is the action-side directory view, `workspace_read` the action-side file view. They are **not** a second `terminal_view` pane; terminal pane viewing stays in the original plugin.
5. Test harmless operations in a disposable project only: inspect `.`, create/read/edit/delete a temporary text file, then `workspace_command("pwd",".")` and `workspace_command("pytest","<disposable-project>")`. Record exact output/errors.
6. When Claude is separately activated, confirm its existing Claude Pocket MCP endpoint uses the same `A25_ZONE1_ROOT`; Claude edits a GPT-created file, GPT rereads and reruns pytest. No claim of this milestone before actual tool calls.

## Limits
The Actions entry is distinct at the ChatGPT connector level but reuses the existing GPT Pocket MCP route. There is no arbitrary shell command tool: `workspace_command` accepts `pwd`, `ls`, `python_version`, `pytest`. File edit replaces full content. Existing source uses local trust; this document neither alters auth nor authorizes phone deployment. Source tests and runtime connector discovery are separate evidence requirements.

## Offline contract check (owner/builder with checkout)
From repository root, execute:
```sh
python -m pytest -q shared/tests/test_zone1_workspace.py
python -m pytest -q shared/tests
python shared/check_zone1_actions_contract.py
```
Report actual exit codes; no test pass is asserted here.
