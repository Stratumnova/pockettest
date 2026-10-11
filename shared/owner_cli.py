"""Local-only owner CLI; no HTTP routes, network listener, or owner token.

Run only from the phone's trusted Termux shell. Owner commands append to
the shared ledger with the same inter-process lock as the server.
"""
from __future__ import annotations
import argparse
import os
from datetime import datetime, timezone

from ledger_lock import ledger_transaction
from ledger_store import read_events, write_event, next_event
from storage import prepare_data_root, resolve_data_root


def _read_events(path):
    return read_events(path)

def append_owner(message, data_root=None):
    """Atomic owner append. This is not exposed through MCP or HTTP."""
    if not isinstance(message, str) or not message.strip() or len(message) > 4096:
        raise ValueError("message must contain 1-4096 characters")
    root = prepare_data_root(resolve_data_root(data_root))
    ledger = root / "roundtable.jsonl"
    with ledger_transaction(root):
        events = _read_events(ledger)
        event = next_event(
            events, author="owner", message=message, references=[],
            cursor_through=events[-1]["id"] if events else 0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        write_event(ledger, event)
    return event["id"]


def main():
    parser = argparse.ArgumentParser(description="Local Shared Space owner CLI")
    parser.add_argument("message", help="Owner message (local shell only)")
    args = parser.parse_args()
    print("owner event id:", append_owner(args.message, os.environ.get("A25_SHARED_DATA")))


if __name__ == "__main__":
    main()
