"""Stage 2 integration checks without modifying any Stage 1 test files."""
import multiprocessing
import os
from pathlib import Path

import pytest

from identity import IdentityConfigurationError
from owner_cli import append_owner, _read_events
from storage import resolve_data_root


def _owner_worker(root, count):
    for n in range(count):
        append_owner(f"worker-{os.getpid()}-{n}", root)


def test_two_processes_unique_monotonic_ids(tmp_path):
    root = str(tmp_path / "data")
    workers = [multiprocessing.Process(target=_owner_worker, args=(root, 25))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)
        assert worker.exitcode == 0
    events = _read_events(Path(root) / "roundtable.jsonl")
    assert [e["id"] for e in events] == list(range(1, 51))
    assert all(e["author"] == "owner" for e in events)
    assert (Path(root) / ".ledger.lock").stat().st_mode & 0o777 == 0o600


def test_factory_refuses_legacy_environment(monkeypatch):
    import server
    monkeypatch.delenv("A25_SHARED_GPT_PATH", raising=False)
    monkeypatch.delenv("A25_SHARED_CLAUDE_PATH", raising=False)
    monkeypatch.setenv("POCKET_GPT_PATH", "X" * 32)
    monkeypatch.setenv("POCKET_CLAUDE_PATH", "Y" * 32)
    with pytest.raises(IdentityConfigurationError):
        server.create_app()


def test_factory_has_no_owner_route(monkeypatch):
    import server
    monkeypatch.setenv("A25_SHARED_GPT_PATH", "A" * 32)
    monkeypatch.setenv("A25_SHARED_CLAUDE_PATH", "B" * 32)
    app = server.create_app()
    assert len(app.routes) == 2
    assert {route.path for route in app.routes} == {"/" + "A" * 32, "/" + "B" * 32}
    assert all("owner" not in route.path for route in app.routes)


def test_owner_cli_rejects_empty_message(tmp_path):
    with pytest.raises(ValueError):
        append_owner("", str(tmp_path / "data"))


def test_server_and_cli_share_lock(tmp_path):
    import asyncio
    import server
    root = tmp_path / "data"
    root.mkdir()
    server.ROOT = root
    server.LEDGER = root / "roundtable.jsonl"
    server.QUARANTINE = root / "quarantine.log"
    server.pending_read = {"gpt": None, "claude": None}
    server.read_logic("gpt")
    assert asyncio.run(server.append_logic("gpt", "hello"))["event_id"] == 1
    assert append_owner("owner note", str(root)) == 2
    server.read_logic("claude")
    assert asyncio.run(server.append_logic("claude", "ack"))["event_id"] == 3
    assert [e["id"] for e in _read_events(root / "roundtable.jsonl")] == [1, 2, 3]
