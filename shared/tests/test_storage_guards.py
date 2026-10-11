import pytest
import server


def test_storage_uninitialized_fails_without_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(server, "ROOT", None)
    monkeypatch.setattr(server, "LEDGER", None)
    monkeypatch.setattr(server, "QUARANTINE", None)

    operations = (
        server._parse_ledger,
        server.recover_once,
        lambda: server._write_event({
            "id": 1,
            "author": "gpt",
            "message": "should not be written",
        }),
    )

    for operation in operations:
        with pytest.raises(
            RuntimeError,
            match="Shared Space storage not initialized",
        ):
            operation()

        assert list(tmp_path.iterdir()) == []


def test_parse_ledger_refuses_symlink(tmp_path, monkeypatch):
    import server

    target = tmp_path / "private.jsonl"
    original = b'{"id":1,"author":"gpt"}\n'
    target.write_bytes(original)

    ledger = tmp_path / "roundtable.jsonl"
    ledger.symlink_to(target)

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", tmp_path / "quarantine.log")

    import pytest

    with pytest.raises(OSError):
        server._parse_ledger()

    assert target.read_bytes() == original
    assert ledger.is_symlink()


def test_write_event_creates_private_ledger(tmp_path, monkeypatch):
    import json
    import stat
    import server

    ledger = tmp_path / "roundtable.jsonl"
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", tmp_path / "quarantine.log")

    event = {"id": 1, "author": "gpt", "message": "hello"}
    server._write_event(event)

    assert ledger.stat().st_mode & 0o777 == 0o600
    assert ledger.read_bytes() == (
        json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def test_write_event_preserves_existing_ledger(tmp_path, monkeypatch):
    import os
    import json
    import server

    ledger = tmp_path / "roundtable.jsonl"
    original = b'{"id":1,"author":"claude"}\n'
    ledger.write_bytes(original)
    os.chmod(ledger, 0o644)

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", tmp_path / "quarantine.log")

    event = {"id": 2, "author": "gpt"}
    server._write_event(event)

    expected = (
        json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")

    assert ledger.read_bytes() == original + expected
    assert ledger.stat().st_mode & 0o777 == 0o600


def test_write_all_partial_and_zero_progress(monkeypatch):
    import os
    import pytest
    import server

    written = bytearray()
    original_write = os.write

    def partial_write(fd, data):
        chunk = bytes(data[:2])
        written.extend(chunk)
        return len(chunk)

    monkeypatch.setattr(server.os, "write", partial_write)
    server._write_all(123, b"abcdef")
    assert bytes(written) == b"abcdef"

    monkeypatch.setattr(server.os, "write", lambda fd, data: 0)
    with pytest.raises(OSError, match="no progress"):
        server._write_all(123, b"abc")

    monkeypatch.setattr(server.os, "write", original_write)


def test_recover_quarantines_exact_tail(tmp_path, monkeypatch):
    import server

    ledger = tmp_path / "roundtable.jsonl"
    quarantine = tmp_path / "quarantine.log"
    good = b'{"id":1,"author":"gpt"}\n'
    tail = b'{"id":2,"author":"claude"'
    ledger.write_bytes(good + tail)

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", quarantine)

    server.recover_once()

    assert ledger.read_bytes() == good
    assert quarantine.read_bytes() == tail + b"\n"
    assert quarantine.stat().st_mode & 0o777 == 0o600


def test_recover_preserves_complete_ledger(tmp_path, monkeypatch):
    import server

    ledger = tmp_path / "roundtable.jsonl"
    original = b'{"id":1}\n{"id":2}\n'
    ledger.write_bytes(original)

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", tmp_path / "quarantine.log")

    server.recover_once()

    assert ledger.read_bytes() == original
    assert not (tmp_path / "quarantine.log").exists()


def test_recover_refuses_symlinked_ledger(tmp_path, monkeypatch):
    import pytest
    import server

    target = tmp_path / "private.jsonl"
    original = b'{"id":1}\npartial'
    target.write_bytes(original)
    ledger = tmp_path / "roundtable.jsonl"
    ledger.symlink_to(target)

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", tmp_path / "quarantine.log")

    with pytest.raises(OSError):
        server.recover_once()

    assert target.read_bytes() == original
    assert ledger.is_symlink()


def test_recover_quarantine_failure_preserves_ledger(tmp_path, monkeypatch):
    import pytest
    import server

    ledger = tmp_path / "roundtable.jsonl"
    original = b'{"id":1}\npartial'
    ledger.write_bytes(original)

    quarantine = tmp_path / "quarantine.log"
    quarantine.mkdir()

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", quarantine)

    with pytest.raises((OSError, ValueError)):
        server.recover_once()

    assert ledger.read_bytes() == original


def test_recover_quarantine_fsync_failure_preserves_ledger(tmp_path, monkeypatch):
    import os
    import pytest
    import server

    ledger = tmp_path / "roundtable.jsonl"
    original = b'{"id":1}\npartial'
    ledger.write_bytes(original)
    quarantine = tmp_path / "quarantine.log"

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "LEDGER", ledger)
    monkeypatch.setattr(server, "QUARANTINE", quarantine)

    real_fsync = os.fsync

    def fail_quarantine_fsync(fd):
        if os.fstat(fd).st_ino == quarantine.stat().st_ino:
            raise OSError("simulated quarantine sync failure")
        return real_fsync(fd)

    monkeypatch.setattr(server.os, "fsync", fail_quarantine_fsync)

    with pytest.raises(OSError, match="simulated quarantine sync failure"):
        server.recover_once()

    assert ledger.read_bytes() == original
    assert quarantine.read_bytes() == b"partial\n"


def test_configure_storage_valid_private_path(tmp_path, monkeypatch):
    import server

    monkeypatch.setattr(server, "ROOT", None)
    monkeypatch.setattr(server, "LEDGER", None)
    monkeypatch.setattr(server, "QUARANTINE", None)

    root = tmp_path / "private"
    server.configure_storage(str(root))

    assert server.ROOT == root.resolve()
    assert server.LEDGER == root / "roundtable.jsonl"
    assert server.QUARANTINE == root / "quarantine.log"
    assert root.stat().st_mode & 0o777 == 0o700

    for path in (server.LEDGER, server.QUARANTINE):
        assert path.is_file()
        assert path.stat().st_mode & 0o777 == 0o600


def test_configure_storage_rejects_bad_paths(tmp_path, monkeypatch):
    import pytest
    import server

    repo = __import__("pathlib").Path(server.__file__).resolve().parents[1]
    cases = ("", "relative/path", str(repo / "forbidden-data"))

    for value in cases:
        monkeypatch.setattr(server, "ROOT", tmp_path)
        monkeypatch.setattr(server, "LEDGER", tmp_path / "old.jsonl")
        monkeypatch.setattr(server, "QUARANTINE", tmp_path / "old.log")

        with pytest.raises(ValueError):
            server.configure_storage(value)

        assert server.ROOT is None
        assert server.LEDGER is None
        assert server.QUARANTINE is None

    assert not (repo / "forbidden-data").exists()
    assert not (tmp_path / "old.jsonl").exists()
    assert not (tmp_path / "old.log").exists()


def test_configure_storage_refuses_symlinked_ledger(tmp_path, monkeypatch):
    import pytest
    import server

    root = tmp_path / "private"
    root.mkdir()

    target = tmp_path / "target.jsonl"
    original = b"private records\n"
    target.write_bytes(original)

    ledger = root / "roundtable.jsonl"
    ledger.symlink_to(target)

    monkeypatch.setattr(server, "ROOT", None)
    monkeypatch.setattr(server, "LEDGER", None)
    monkeypatch.setattr(server, "QUARANTINE", None)

    with pytest.raises(OSError):
        server.configure_storage(str(root))

    assert server.ROOT is None
    assert server.LEDGER is None
    assert server.QUARANTINE is None
    assert ledger.is_symlink()
    assert target.read_bytes() == original
    assert not (root / "quarantine.log").exists()
