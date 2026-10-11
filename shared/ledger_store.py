"""Shared ledger primitives for both HTTP server and local owner CLI.

Caller must hold ledger_transaction(root) across read/compute/append.
"""
from __future__ import annotations
import json
import os
from secure_files import secure_append, secure_read


def read_events(path, *, allow_incomplete=False):
    try:
        with secure_read(path) as fd:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except FileNotFoundError:
        return []
    raw = b"".join(chunks)
    if raw and not raw.endswith(b"\n"):
        if not allow_incomplete:
            raise RuntimeError("incomplete ledger tail: server recovery required")
        raw = raw[:raw.rfind(b"\n") + 1]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def write_all(fd, data):
    view = memoryview(data)
    while view:
        count = os.write(fd, view)
        if count <= 0:
            raise OSError("Storage write made no progress")
        view = view[count:]


def write_event(path, event):
    data = (json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    with secure_append(path) as fd:
        write_all(fd, data)
        os.fsync(fd)


def next_event(events, *, author, message, references, cursor_through, timestamp):
    return {
        "id": events[-1]["id"] + 1 if events else 1,
        "author": author,
        "ts": timestamp,
        "message": message,
        "references": references,
        "cursor_through": cursor_through,
    }
