"""Pocket Server Gate-01: dummy-data-only MCP Roundtable proof."""
from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP

ROOT=Path(os.environ.get("POCKET_GATE_DIR",".")).resolve()
LEDGER=ROOT/"roundtable.jsonl"
QUARANTINE=ROOT/"quarantine.log"
LOCK=asyncio.Lock()
pending_read={"gpt":None,"claude":None}

def _load()->list[dict[str,Any]]:
    if not LEDGER.exists(): return []
    raw=LEDGER.read_bytes()
    if raw and not raw.endswith(b"\n"):
        cut=raw.rfind(b"\n")+1
        bad=raw[cut:]
        if bad:
            with QUARANTINE.open("ab") as q: q.write(bad+b"\n")
        LEDGER.write_bytes(raw[:cut])
        raw=raw[:cut]
    out=[]
    for line in raw.splitlines():
        if line.strip(): out.append(json.loads(line))
    return out

def _cursor(events, who):
    mine=[e for e in events if e["author"]==who]
    return int(mine[-1].get("cursor_through",0)) if mine else 0

def _last_mine(events,who):
    for e in reversed(events):
        if e["author"]==who:return e
    return None

def _write_event(e):
    ROOT.mkdir(parents=True,exist_ok=True)
    with LEDGER.open("ab") as f:
        f.write((json.dumps(e,separators=(",",":"),ensure_ascii=False)+"\n").encode())
        f.flush(); os.fsync(f.fileno())

def make_server(who:str):
    mcp=FastMCP(f"Pocket Gate {who}",stateless_http=True,json_response=True)

    @mcp.tool()
    def server_status():
        return {"server":"Pocket Server Gate-01","protocol":"roundtable-v1",
                "identity":who,"transport":"streamable-http",
                "auth_mode":"gate-path","dummy_data_only":True}

    @mcp.tool()
    def read_roundtable():
        events=_load(); cursor=_cursor(events,who)
        seen=[e for e in events if e["id"]<=cursor]
        unseen=[e for e in events if e["id"]>cursor and e["author"]!=who]
        pending_read[who]=events[-1]["id"] if events else 0
        return {"context":seen[-3:],"unseen":unseen,
                "latest_event_id":pending_read[who]}

    @mcp.tool()
    async def append_roundtable(message:str,references:list[str]|None=None):
        refs=references or []
        async with LOCK:
            events=_load()
            if pending_read[who] is None:
                last=_last_mine(events,who)
                if last and last["message"]==message and last.get("references",[])==refs:
                    return {"ok":True,"event_id":last["id"],"duplicate":True}
                return {"ok":False,"error":"read first"}
            through=int(pending_read[who])
            event={"id":(events[-1]["id"]+1 if events else 1),"author":who,
                   "ts":datetime.now(timezone.utc).isoformat(),
                   "message":message,"references":refs,"cursor_through":through}
            _write_event(event)
            pending_read[who]=None
            return {"ok":True,"event_id":event["id"],"duplicate":False}
    return mcp

# Run one identity per process/secret URL. This prevents identity being a tool argument.
IDENTITY=os.environ.get("POCKET_IDENTITY","gpt").lower()
if IDENTITY not in {"gpt","claude"}: raise SystemExit("POCKET_IDENTITY must be gpt or claude")
app=make_server(IDENTITY).streamable_http_app()
