import os
import stat
import subprocess
import sys

import pytest

from secure_files import secure_append


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_new_file_private(tmp_path):
    path = tmp_path / "ledger.jsonl"
    with secure_append(path) as fd:
        os.write(fd, b"first\n")
        os.fsync(fd)
    assert mode(path) == 0o600
    assert path.read_bytes() == b"first\n"


def test_existing_file_preserved(tmp_path):
    path = tmp_path / "ledger.jsonl"
    original = b"existing ledger\n"
    path.write_bytes(original)
    os.chmod(path, 0o644)

    with secure_append(path):
        pass

    assert mode(path) == 0o600
    assert path.read_bytes() == original


def test_symlink_refused(tmp_path):
    target = tmp_path / "target"
    target.write_bytes(b"untouched")
    link = tmp_path / "ledger.jsonl"
    link.symlink_to(target)

    with pytest.raises(OSError):
        with secure_append(link):
            pass

    assert target.read_bytes() == b"untouched"


def test_directory_refused(tmp_path):
    with pytest.raises((OSError, ValueError)):
        with secure_append(tmp_path):
            pass


def test_fifo_refused_without_hanging(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)

    script = """
import sys
sys.path.insert(0, sys.argv[2])
from secure_files import secure_append
try:
    with secure_append(sys.argv[1]):
        pass
except (OSError, ValueError):
    sys.exit(0)
sys.exit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(fifo),
            str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        ],
        capture_output=True,
        text=True,
        timeout=3,
    )

    assert result.returncode == 0, result.stderr


# Secure-read tests
from secure_files import secure_read


def test_secure_read_existing_file(tmp_path):
    path = tmp_path / "ledger.jsonl"
    original = b'{"id":1}\n{"id":2}\n'
    path.write_bytes(original)

    with secure_read(path) as fd:
        chunks = []
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            chunks.append(chunk)

    assert b"".join(chunks) == original


def test_secure_read_missing_file(tmp_path):
    path = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        with secure_read(path):
            pass
    assert not path.exists()


def test_secure_read_symlink_refused(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_bytes(b"private data")
    link = tmp_path / "link.jsonl"
    link.symlink_to(target)

    with pytest.raises(OSError):
        with secure_read(link):
            pass

    assert target.read_bytes() == b"private data"


def test_secure_read_directory_refused(tmp_path):
    with pytest.raises((OSError, ValueError)):
        with secure_read(tmp_path):
            pass


def test_secure_read_fifo_refused_without_hanging(tmp_path):
    fifo = tmp_path / "read_fifo"
    os.mkfifo(fifo)

    script = """
import sys
sys.path.insert(0, sys.argv[2])
from secure_files import secure_read
try:
    with secure_read(sys.argv[1]):
        pass
except ValueError:
    sys.exit(0)
sys.exit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(fifo),
            str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        ],
        capture_output=True,
        text=True,
        timeout=3,
    )

    assert result.returncode == 0, result.stderr


# Secure read-write tests
from secure_files import secure_rdwr


def test_secure_rdwr_existing_file(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_bytes(b"original")

    with secure_rdwr(path) as fd:
        assert os.read(fd, 8) == b"original"
        os.lseek(fd, 0, os.SEEK_END)
        os.write(fd, b"-updated")

    assert path.read_bytes() == b"original-updated"


def test_secure_rdwr_missing_file(tmp_path):
    path = tmp_path / "missing.jsonl"

    with pytest.raises(FileNotFoundError):
        with secure_rdwr(path):
            pass

    assert not path.exists()


def test_secure_rdwr_symlink_refused(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_bytes(b"private")
    link = tmp_path / "link.jsonl"
    link.symlink_to(target)

    with pytest.raises(OSError):
        with secure_rdwr(link):
            pass

    assert target.read_bytes() == b"private"
    assert link.is_symlink()


def test_secure_rdwr_directory_refused(tmp_path):
    with pytest.raises((OSError, ValueError)):
        with secure_rdwr(tmp_path):
            pass


def test_secure_rdwr_fifo_refused_without_hanging(tmp_path):
    fifo = tmp_path / "rdwr_fifo"
    os.mkfifo(fifo)

    script = """
import sys
sys.path.insert(0, sys.argv[2])
from secure_files import secure_rdwr
try:
    with secure_rdwr(sys.argv[1]):
        pass
except ValueError:
    sys.exit(0)
sys.exit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(fifo),
            str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        ],
        capture_output=True,
        text=True,
        timeout=3,
    )

    assert result.returncode == 0, result.stderr
