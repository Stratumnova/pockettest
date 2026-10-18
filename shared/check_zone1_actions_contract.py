"""Offline source contract check for the separately configured Zone 1 Actions connector.

Does not contact a phone, server, tunnel, or ChatGPT connector.
"""
from pathlib import Path
import json
import re

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / "zone1_actions_entry.json").read_text(encoding="utf-8"))
server = (HERE / "server.py").read_text(encoding="utf-8")
workspace = (HERE / "zone1_workspace.py").read_text(encoding="utf-8")
assert manifest["kind"] == "mcp-streamable-http"
assert manifest["connection"]["requires_new_server"] is False
assert manifest["connection"]["requires_new_route"] is False
assert 'GPT=make_mcp("gpt")' in server
assert "Mount(GPT_PATH,app=GPT.streamable_http_app())" in server
names = [t["name"] for t in manifest["tools"]]
assert len(names) == len(set(names)) == 6
for name in names:
    assert re.search(r"def\s+" + re.escape(name) + r"\s*\(", server), name
assert all(action in workspace for action in manifest["allowed_command_actions"])
print("SOURCE CONTRACT PASS: six workspace tools registered on existing GPT MCP route")
print("NOT VERIFIED: ChatGPT connector installation, phone runtime, tests, cross-seat access")
