"""Pocket Server Gate-01 — dummy-data-only MCP Roundtable proof."""
from __future__ import annotations
import asyncio, json, os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

ROOT=Path(os.environ.get("POCKET_GATE_DIR",".")).resolve()
LEDGER=ROOT/"roundtable.jsonl"; QUARANTINE=ROOT/"quarantine.log"
LOCK=asyncio.Lock()
pending_read={"gpt":None,"claude":None}

def _parse_ledger()->list[dict[str,Any]]:
    if not LEDGER.exists(): return []
    raw=LEDGER.read_bytes()
    # Parse only complete newline-terminated records. Never repair during a read.
    cut = len(raw) if raw.endswith(b"\n") else raw.rfind(b"\n") + 1
    return [json.loads(x) for x in raw[:cut].splitlines() if x.strip()]

def recover_once():
    ROOT.mkdir(parents=True,exist_ok=True)
    if not LEDGER.exists(): return
    raw=LEDGER.read_bytes()
    if raw and not raw.endswith(b"\n"):
        cut=raw.rfind(b"\n")+1; bad=raw[cut:]
        if bad:
            with QUARANTINE.open("ab") as q: q.write(bad+b"\n")
        with LEDGER.open("r+b") as f: f.truncate(cut); f.flush(); os.fsync(f.fileno())

def _cursor(events,who):
    mine=[e for e in events if e["author"]==who]
    return int(mine[-1].get("cursor_through",0)) if mine else 0

def _last_mine(events,who):
    return next((e for e in reversed(events) if e["author"]==who),None)

def _write_event(e):
    ROOT.mkdir(parents=True,exist_ok=True)
    with LEDGER.open("ab") as f:
        f.write((json.dumps(e,separators=(",",":"),ensure_ascii=False)+"\n").encode())
        f.flush(); os.fsync(f.fileno())

def status(who):
    return {"server":"Pocket Server Gate-01","protocol":"roundtable-v1","identity":who,
            "transport":"streamable-http","auth_mode":"gate-path","dummy_data_only":True}

def read_logic(who):
    events=_parse_ledger(); cursor=_cursor(events,who)
    unseen=[e for e in events if e["id"]>cursor and e["author"]!=who]
    unseen_ids={e["id"] for e in unseen}
    context=[e for e in events if e["id"] not in unseen_ids][-3:]
    pending_read[who]=events[-1]["id"] if events else 0
    return {"context":context,"unseen":unseen,"latest_event_id":pending_read[who]}

async def append_logic(who,message,references=None):
    refs=references or []
    async with LOCK:
        events=_parse_ledger()
        if pending_read[who] is None:
            last=_last_mine(events,who)
            if last and last["message"]==message and last.get("references",[])==refs:
                return {"ok":True,"event_id":last["id"],"duplicate":True}
            return {"ok":False,"error":"read first"}
        through=int(pending_read[who])
        event={"id":(events[-1]["id"]+1 if events else 1),"author":who,
               "ts":datetime.now(timezone.utc).isoformat(),"message":message,
               "references":refs,"cursor_through":through}
        _write_event(event); pending_read[who]=None
        return {"ok":True,"event_id":event["id"],"duplicate":False}

def _transport_security():
    hosts=["127.0.0.1:*","localhost:*","[::1]:*"]
    extra=[h.strip().lower() for h in os.environ.get("POCKET_ALLOWED_HOSTS","").split(",") if h.strip()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts+extra,
        allowed_origins=[f"https://{h}" for h in extra],
    )

def make_mcp(who):
    m=FastMCP(f"Pocket Gate {who}",stateless_http=True,json_response=True,
              transport_security=_transport_security())
    @m.tool()
    def server_status(): return status(who)
    @m.tool()
    def read_roundtable(): return read_logic(who)
    @m.tool()
    async def append_roundtable(message:str,references:list[str]|None=None):
        return await append_logic(who,message,references)
    return m

GPT=make_mcp("gpt"); CLAUDE=make_mcp("claude")
def _secret_path(name):
    value=os.environ.get(name,"").strip("/")
    if len(value)<24 or "CHANGE-ME" in value.upper():
        raise SystemExit(f"{name} must be a random path of at least 24 characters")
    return "/"+value

GPT_PATH=_secret_path("POCKET_GPT_PATH")
CLAUDE_PATH=_secret_path("POCKET_CLAUDE_PATH")
if GPT_PATH==CLAUDE_PATH:
    raise SystemExit("GPT and Claude paths must differ")

@asynccontextmanager
async def lifespan(app):
    async with LOCK: recover_once()
    async with GPT.session_manager.run(), CLAUDE.session_manager.run():
        yield

app=Starlette(routes=[
    Mount(GPT_PATH,app=GPT.streamable_http_app()),
    Mount(CLAUDE_PATH,app=CLAUDE.streamable_http_app()),
],lifespan=lifespan)
