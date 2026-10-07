import asyncio, tempfile
from pathlib import Path
import server

def reset(p):
    server.ROOT=Path(p); server.LEDGER=server.ROOT/"roundtable.jsonl"; server.QUARANTINE=server.ROOT/"quarantine.log"
    server.pending_read={"gpt":None,"claude":None}

# Storage-level smoke checks; connector calls are the real Gate-01 acceptance test.
def test_cursor_reconstruction():
    with tempfile.TemporaryDirectory() as d:
        reset(d)
        server._write_event({"id":1,"author":"claude","ts":"x","message":"a","references":[],"cursor_through":0})
        server._write_event({"id":2,"author":"gpt","ts":"x","message":"b","references":[],"cursor_through":1})
        ev=server._load()
        assert server._cursor(ev,"gpt")==1
        assert server._cursor(ev,"claude")==0

def test_truncated_tail_quarantine():
    with tempfile.TemporaryDirectory() as d:
        reset(d)
        server.ROOT.mkdir()
        server.LEDGER.write_bytes(b'{"id":1,"author":"gpt","cursor_through":0}\n{"id":2')
        ev=server._load()
        assert len(ev)==1
        assert server.QUARANTINE.exists()
