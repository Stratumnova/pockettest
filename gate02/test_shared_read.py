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
            small = Path(tmp) / "small"
            small.write_bytes(b"valid")
            link = Path(tmp) / "link"
            link.symlink_to(small)
            self.assertEqual(self.server.read_fixed_file(str(link)), {"error": "shared_file_unavailable"})

    def test_default_deny_all_and_single_read_tool(self):
        self.assertFalse(self.server.LOCAL_READ_MODE, "Unset A25_LOCAL_READ_MODE for default-deny test")
        import asyncio
        tools = asyncio.run(self.server.mcp.list_tools())
        self.assertEqual([tool.name for tool in tools], ["read_shared_file"])

    def test_sdk_asgi_modes(self):
        """Exercise real MCP ASGI authorization, metadata, loopback and headers."""
        import subprocess
        import sys
        import textwrap
        script = textwrap.dedent("""
            import asyncio, importlib.util, json, os, sys
            import httpx
            from pathlib import Path
            p = Path(sys.argv[1])
            sys.path.insert(0, str(p.parent))
            spec = importlib.util.spec_from_file_location("gate02_sdk_case", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert mod.LOCAL_READ_MODE == (os.environ.get("A25_LOCAL_READ_MODE") == "1")
            async def main():
                async with mod.mcp.session_manager.run():
                    async def request(client, host="localhost", extra=None):
                        transport = httpx.ASGITransport(app=mod.app, client=(client, 12345))
                        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
                            headers = {"host": host, "accept": "application/json, text/event-stream",
                                       "content-type": "application/json", "mcp-protocol-version": "2025-06-18"}
                            headers.update(extra or {})
                            return await c.post("/mcp", headers=headers,
                                json={"jsonrpc":"2.0","id":1,"method":"initialize",
                                      "params":{"protocolVersion":"2025-06-18",
                                      "capabilities":{},"clientInfo":{"name":"test","version":"1"}}})
                    if not mod.LOCAL_READ_MODE:
                        r = await request("127.0.0.1")
                        assert r.status_code == 401, (r.status_code, r.text)
                        transport = httpx.ASGITransport(app=mod.app, client=("127.0.0.1", 12345))
                        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
                            health = await c.get("/health")
                            assert health.json() == {"status":"gate02a-deny-all","ready":False}
                            metadata = await c.get("/.well-known/oauth-authorization-server")
                            assert metadata.status_code == 200, (metadata.status_code, metadata.text)
                    else:
                        assert (await request("127.0.0.1")).status_code == 200
                        assert (await request("203.0.113.5")).status_code == 403
                        assert (await request("127.0.0.1", host="roundtable.rodsrcpark.com")).status_code == 403
                        for name in ("cf-connecting-ip","cf-ray","x-forwarded-for","forwarded","x-real-ip"):
                            assert (await request("127.0.0.1", extra={name:"203.0.113.5"})).status_code == 403, name
                        transport = httpx.ASGITransport(app=mod.app, client=("127.0.0.1", 12345))
                        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
                            health = await c.get("/health", headers={"host":"localhost"})
                            assert health.json() == {"status":"gate02a-local-read","ready":False}
            asyncio.run(main())
        """)
        for mode in ("0", "1"):
            env = dict(os.environ, A25_LOCAL_READ_MODE=mode)
            result = subprocess.run([sys.executable, "-c", script, str(SERVER)],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0,
                             "mode=" + mode + "\\n" + result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
