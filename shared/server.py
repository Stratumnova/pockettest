"""Pocket Server Gate-01 — dummy-data-only MCP Roundtable proof."""
from __future__ import annotations
import asyncio, json, os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from secure_files import secure_read, secure_append, secure_rdwr
from ledger_lock import ledger_transaction
from identity import load_identities
from storage import resolve_data_root, prepare_data_root
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

# Configured during lifespan startup, never at import.
ROOT = None
LEDGER = None
QUARANTINE = None
LOCK=asyncio.Lock()
pending_read={"gpt":None,"claude":None}

def _require_storage():
    if ROOT is None or LEDGER is None or QUARANTINE is None:
        raise RuntimeError("Shared Space storage not initialized")
    return ROOT, LEDGER, QUARANTINE


def _parse_ledger()->list[dict[str,Any]]:
    _require_storage()
    try:
        with secure_read(LEDGER) as fd:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except FileNotFoundError:
        return []

    raw = b"".join(chunks)
    # Parse only complete newline-terminated records. Never repair during a read.
    cut = len(raw) if raw.endswith(b"\n") else raw.rfind(b"\n") + 1
    return [json.loads(x) for x in raw[:cut].splitlines() if x.strip()]


def recover_once():
    _require_storage()

    try:
        with secure_rdwr(LEDGER) as fd:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)

            raw = b"".join(chunks)
            if not raw or raw.endswith(b"\n"):
                return

            cut = raw.rfind(b"\n") + 1
            bad = raw[cut:]

            if bad:
                with secure_append(QUARANTINE) as qfd:
                    _write_all(qfd, bad + b"\n")
                    os.fsync(qfd)

            os.ftruncate(fd, cut)
            os.fsync(fd)

    except FileNotFoundError:
        if not LEDGER.exists():
            return
        raise



def _cursor(events,who):
    mine=[e for e in events if e["author"]==who]
    return int(mine[-1].get("cursor_through",0)) if mine else 0

def _last_mine(events,who):
    return next((e for e in reversed(events) if e["author"]==who),None)

def _write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("Storage write made no progress")
        view = view[written:]


def _write_event(e):
    _require_storage()
    data = (
        json.dumps(e, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")

    with secure_append(LEDGER) as fd:
        _write_all(fd, data)
        os.fsync(fd)


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
      with ledger_transaction(ROOT):
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

def configure_storage(env_value):
    global ROOT, LEDGER, QUARANTINE

    ROOT = None
    LEDGER = None
    QUARANTINE = None

    root = prepare_data_root(resolve_data_root(env_value))
    ledger = root / "roundtable.jsonl"
    quarantine = root / "quarantine.log"

    with ledger_transaction(root):
        for path in (ledger, quarantine):
            with secure_append(path):
                pass

    ROOT, LEDGER, QUARANTINE = root, ledger, quarantine


def create_app():
    """Build routes from fresh runtime secrets; no import-time credential reads."""
    identities = load_identities()
    gpt = make_mcp("gpt")
    claude = make_mcp("claude")

    @asynccontextmanager
    async def lifespan(app):
        configure_storage(os.environ.get("A25_SHARED_DATA"))
        async with LOCK:
            with ledger_transaction(ROOT):
                recover_once()
        async with gpt.session_manager.run(), claude.session_manager.run():
            yield

    return Starlette(routes=[
        Mount(identities.gpt_path, app=gpt.streamable_http_app()),
        Mount(identities.claude_path, app=claude.streamable_http_app()),
    ], lifespan=lifespan)
