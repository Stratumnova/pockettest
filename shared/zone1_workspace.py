"""Zone 1 local workspace operations. Local-trust prototype; not an authorization boundary."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

MAX_BYTES = 1_000_000
TIMEOUT = 30

class Workspace:
    def __init__(self, root):
        if not root:
            raise ValueError("A25_ZONE1_ROOT is required")
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_absolute():
            raise ValueError("workspace root must be absolute")
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative, existing=False):
        if not isinstance(relative, str) or not relative or "\\x00" in relative:
            raise ValueError("invalid relative path")
        p = Path(relative)
        if p.is_absolute() or ".." in p.parts or p == Path("."):
            raise ValueError("path must be relative and inside workspace")
        candidate = self.root / p
        # Resolve symlinks in all existing path components.
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("path escapes workspace")
        if existing and not resolved.exists():
            raise FileNotFoundError(relative)
        return resolved

    def inspect(self, path="."):
        target = self.root if path == "." else self.path(path, True)
        if not target.is_dir():
            raise NotADirectoryError(path)
        return {"path": path, "entries": [
            {"name": p.name, "type": "directory" if p.is_dir() else "file" if p.is_file() else "other"}
            for p in sorted(target.iterdir(), key=lambda x: x.name) if not p.is_symlink()
        ]}

    def read(self, path):
        target = self.path(path, True)
        if not target.is_file() or target.stat().st_size > MAX_BYTES:
            raise ValueError("not a regular file or exceeds size limit")
        return {"path": path, "content": target.read_text(encoding="utf-8")}

    def write(self, path, content, overwrite=False):
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
            raise ValueError("content exceeds limit or is not text")
        target = self.path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = self.path(path)  # recheck after parent creation
        if target.exists() and not overwrite:
            raise FileExistsError(path)
        if target.exists() and not target.is_file():
            raise ValueError("not a regular file")
        with target.open("w" if overwrite else "x", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}

    def delete(self, path):
        target = self.path(path, True)
        if not target.is_file():
            raise ValueError("only regular files may be deleted")
        target.unlink()
        return {"ok": True, "path": path}

    def command(self, action, path="."):
        cwd = self.root if path == "." else self.path(path, True)
        if not cwd.is_dir():
            raise NotADirectoryError(path)
        commands = {
            "pwd": ["pwd"],
            "ls": ["ls", "-la"],
            "python_version": ["python", "--version"],
            "pytest": ["python", "-m", "pytest", "-q"],
        }
        if action not in commands:
            raise ValueError("unsupported action; choose pwd, ls, python_version, pytest")
        try:
            result = subprocess.run(commands[action], cwd=cwd, capture_output=True,
                                    text=True, timeout=TIMEOUT, check=False)
            return {"action": action, "exit_code": result.returncode,
                    "stdout": result.stdout[:65536], "stderr": result.stderr[:65536]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"action": action, "exit_code": None, "stdout": "",
                    "stderr": str(exc)}
