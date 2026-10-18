"""Focused Gate-02A fixed-file read tests; run: python -m unittest gate02/test_shared_read.py."""
import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SERVER = Path(__file__).with_name("server.py")


def load_server():
    # This module needs the dependencies in gate02/requirements.lock.txt.
    import sys
    sys.path.insert(0, str(SERVER.parent))
    spec = importlib.util.spec_from_file_location("a25_gate02_test", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_server()

    def test_exact_bytes_hash_and_length(self):
        payload = b"\x00\xff\xfeA25\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(payload)
            result = self.server.read_fixed_file(str(path))
            self.assertEqual(base64.b64decode(result["content_base64"]), payload)
            self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(result["byte_length"], len(payload))

    def test_missing_and_unconfigured(self):
        self.assertEqual(self.server.read_fixed_file(None), {"error": "shared_file_unavailable"})
        self.assertEqual(self.server.read_fixed_file("relative"), {"error": "shared_file_unavailable"})
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.server.read_fixed_file(str(Path(tmp) / "missing")), {"error": "shared_file_unavailable"})

    def test_symlink_and_size_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample"
            path.write_bytes(b"x" * (self.server.MAX_SHARED_BYTES + 1))
            self.assertEqual(self.server.read_fixed_file(str(path)), {"error": "shared_file_unavailable"})
            link = Path(tmp) / "link"
            link.symlink_to(path)
            self.assertEqual(self.server.read_fixed_file(str(link)), {"error": "shared_file_unavailable"})

    def test_default_deny_all_and_single_read_tool(self):
        self.assertFalse(self.server.LOCAL_READ_MODE, "Unset A25_LOCAL_READ_MODE for default-deny test")
        self.assertIsInstance(self.server.provider, self.server.DenyAllProvider)
        import asyncio
        tools = asyncio.run(self.server.mcp.list_tools())
        self.assertEqual([tool.name for tool in tools], ["read_shared_file"])


if __name__ == "__main__":
    unittest.main()
