import asyncio,tempfile
from pathlib import Path
import server

def reset(p):
    server.ROOT=Path(p); server.LEDGER=server.ROOT/"roundtable.jsonl"; server.QUARANTINE=server.ROOT/"quarantine.log"
    server.pending_read={"gpt":None,"claude":None}; server.ROOT.mkdir(exist_ok=True)

def test_interleaving_and_own_filter():
    with tempfile.TemporaryDirectory() as d:
        reset(d)
        assert server.read_logic("gpt")["unseen"]==[]
        assert server.read_logic("claude")["unseen"]==[]
        asyncio.run(server.append_logic("claude","c1"))
        asyncio.run(server.append_logic("gpt","g1"))
        r=server.read_logic("gpt")
        assert [e["message"] for e in r["unseen"]]==["c1"]
        assert "g1" in [e["message"] for e in r["context"]]

def test_append_requires_read_and_retry():
    with tempfile.TemporaryDirectory() as d:
        reset(d)
        assert asyncio.run(server.append_logic("gpt","x"))["error"]=="read first"
        server.read_logic("gpt")
        first=asyncio.run(server.append_logic("gpt","x"))
        retry=asyncio.run(server.append_logic("gpt","x"))
        assert retry["duplicate"] and retry["event_id"]==first["event_id"]

def test_restart_reconstructs_cursor():
    with tempfile.TemporaryDirectory() as d:
        reset(d); server.read_logic("gpt"); asyncio.run(server.append_logic("gpt","g"))
        server.pending_read={"gpt":None,"claude":None}
        assert server._cursor(server._parse_ledger(),"gpt")==0

def test_truncated_tail_quarantine():
    with tempfile.TemporaryDirectory() as d:
        reset(d)
        server.LEDGER.write_bytes(b'{"id":1,"author":"gpt","cursor_through":0}\n{"id":2')
        server.recover_once()
        ev=server._parse_ledger()
        assert len(ev)==1 and server.QUARANTINE.exists()
