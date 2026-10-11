"""Cross-process ledger transaction lock shared by server and local owner CLI."""
from __future__ import annotations
import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def ledger_transaction(root):
    """Exclusive flock around the entire read/compute/append operation.

    The lock inode must not be deleted or replaced while processes run.
    """
    root = Path(root)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(root / ".ledger.lock", flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("ledger lock must be a single-link regular file")
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
