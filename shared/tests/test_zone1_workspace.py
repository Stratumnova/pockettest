import tempfile
from pathlib import Path
import pytest
from zone1_workspace import Workspace

def test_shared_lifecycle():
    with tempfile.TemporaryDirectory() as d:
        w = Workspace(d)
        assert w.write("Shared/demo.py", "print(42)")["ok"]
        assert w.read("Shared/demo.py")["content"] == "print(42)"
        with pytest.raises(FileExistsError):
            w.write("Shared/demo.py", "bad")
        assert w.write("Shared/demo.py", "print(43)", overwrite=True)["ok"]
        assert w.read("Shared/demo.py")["content"] == "print(43)"
        assert w.inspect("Shared")["entries"][0]["name"] == "demo.py"
        assert w.command("pwd")["exit_code"] == 0
        assert w.command("python_version")["exit_code"] == 0
        assert w.command("ls", "Shared")["exit_code"] == 0
        assert w.delete("Shared/demo.py")["ok"]
        with pytest.raises(FileNotFoundError):
            w.read("Shared/demo.py")

def test_reject_escape_and_unlisted_commands():
    with tempfile.TemporaryDirectory() as d:
        w = Workspace(d)
        for path in ("../escape", "/etc/passwd"):
            with pytest.raises(ValueError):
                w.read(path)
        with pytest.raises(ValueError):
            w.command("sh")
        outside = Path(d).parent / "external-zone1-test"
        (Path(d) / "link").symlink_to(outside)
        with pytest.raises(ValueError):
            w.write("link/file.txt", "x")

def test_reject_relative_root_and_nul_path():
    with pytest.raises(ValueError, match="absolute"):
        Workspace("relative-zone1-root")
    with tempfile.TemporaryDirectory() as d:
        w = Workspace(d)
        with pytest.raises(ValueError, match="invalid relative path"):
            w.read("bad" + chr(0) + "path")
