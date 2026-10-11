"""Secure append access for A25 Shared Space."""
import os
import stat
from contextlib import contextmanager


@contextmanager
def secure_append(path):
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NOCTTY", "O_NONBLOCK")

    for name in required:
        if not hasattr(os, name):
            raise RuntimeError(f"{name} is required")

    flags = (
        os.O_WRONLY
        | os.O_APPEND
        | os.O_CREAT
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NOCTTY
        | os.O_NONBLOCK
    )

    fd = os.open(path, flags, 0o600)

    try:
        info = os.fstat(fd)

        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Storage target must be a regular file")

        os.fchmod(fd, 0o600)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def secure_read(path):
    """Open a regular file for reading without following final symlinks."""
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NOCTTY", "O_NONBLOCK")

    for name in required:
        if not hasattr(os, name):
            raise RuntimeError(f"{name} is required")

    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NOCTTY
        | os.O_NONBLOCK
    )

    fd = os.open(path, flags)

    try:
        info = os.fstat(fd)

        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Storage target must be a regular file")

        yield fd
    finally:
        os.close(fd)


@contextmanager
def secure_rdwr(path):
    """Open an existing regular file for read/write without following symlinks."""
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NOCTTY", "O_NONBLOCK")

    for name in required:
        if not hasattr(os, name):
            raise RuntimeError(f"{name} is required")

    flags = (
        os.O_RDWR
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NOCTTY
        | os.O_NONBLOCK
    )

    fd = os.open(path, flags)

    try:
        info = os.fstat(fd)

        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Storage target must be a regular file")

        yield fd
    finally:
        os.close(fd)
