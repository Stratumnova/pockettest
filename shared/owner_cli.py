"""Local-only owner CLI; no HTTP routes, network listener, or owner token.

Run only from the phone's trusted Termux shell. Owner commands append to
the shared ledger with the same inter-process lock as the server.
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone

from ledger_lock import ledger_transaction
from secure_files import secure_append, secure_read
from storage import prepare_data_root, resolve_data_root


def _read_events(path):
    try:
        with secure_read(path) as fd:
            with os.fdopen(os.dup(fd), "rb") as stream:
                raw = stream.read()
    except FileNotFoundError:
        return []
    if raw and not raw.endswith(b"\n"):
        raise RuntimeError("incomplete ledger tail: server recovery required")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def append_owner(message, data_root=None):
    """Atomic owner append. This is not exposed through MCP or HTTP."""
    if not isinstance(message, str) or not message.strip() or len(message) > 4096:
        raise ValueError("message must contain 1-4096 characters")
    root = prepare_data_root(resolve_data_root(data_root))
    ledger = root / "roundtable.jsonl"
    with ledger_transaction(root):
        events = _read_events(ledger)
        event = {
            "id": events[-1]["id"] + 1 if events else 1,
            "author": "owner",
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "references": [],
            "cursor_through": events[-1]["id"] if events else 0,
        }
        data = (json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        with secure_append(ledger) as fd:
            view = memoryview(data)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise OSError("ledger append stalled")
                view = view[count:]
            os.fsync(fd)
    return event["id"]


def main():
    parser = argparse.ArgumentParser(description="Local Shared Space owner CLI")
    parser.add_argument("message", help="Owner message (local shell only)")
    args = parser.parse_args()
    print("owner event id:", append_owner(args.message, os.environ.get("A25_SHARED_DATA")))


if __name__ == "__main__":
    main()
