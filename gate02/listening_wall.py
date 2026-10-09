"""A5-prep experiment helpers. No credentials, authorization, or persistent clients."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

LOG_PATH = Path(__file__).with_name("observations.jsonl")
LOG_MAX_BYTES = 1_000_000
FIELDS = ("redirect_uris", "token_endpoint_auth_method", "grant_types",
          "response_types", "scope", "client_name", "client_uri", "logo_uri",
          "software_id", "software_version")
_lock = asyncio.Lock()


def _bounded(value):
    if isinstance(value, (list, tuple)):
        value = list(value[:10])
    try:
        return json.dumps(value, ensure_ascii=True, default=str)[:300]
    except Exception:
        return "<unserializable>"


async def observe(kind, client_info=None, client_id=None):
    try:
        record = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind}
        if client_info is not None:
            record["fields"] = {}
            for name in FIELDS:
                value = getattr(client_info, name, None)
                if value is not None:
                    record["fields"][name] = _bounded(value)
        if client_id is not None:
            try:
                parts = urlsplit(str(client_id))
                if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password:
                    record["client_id"] = (f"https://{parts.hostname}" +
                                           (f":{parts.port}" if parts.port else "") +
                                           parts.path)[:300]
                else:
                    record["client_id"] = "non-URL id"
            except (ValueError, TypeError):
                record["client_id"] = "non-URL id"
        line = (json.dumps(record, ensure_ascii=True) + "\n").encode()
        try:
            async with _lock:
                fd = os.open(LOG_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                try:
                    os.fchmod(fd, 0o600)
                    if os.fstat(fd).st_size + len(line) <= LOG_MAX_BYTES:
                        os.write(fd, line)
                finally:
                    os.close(fd)
        except OSError:
            pass  # Observation failure never changes deny-all decisions.
    
    except Exception:
        pass  # Observation failure never changes deny-all decisions.

class BodyLimitMiddleware:
    """Buffer selected HTTP bodies before calling app; reject oversized bodies."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope.get("path", ""), scope.get("method", "").upper()
        limit = (1_048_576 if path == "/mcp" and method == "POST" else
                 16_384 if path in ("/register", "/token", "/authorize", "/revoke")
                 and method == "POST" else None)
        if limit is None:
            return await self.app(scope, receive, send)
        lengths = [v for k, v in scope.get("headers", []) if k.lower() == b"content-length"]
        try:
            declared = int(lengths[0]) if len(lengths) == 1 else (None if not lengths else -1)
            invalid = declared is not None and (declared < 0 or str(declared).encode() != lengths[0].strip())
        except ValueError:
            invalid, declared = True, None
        async def reject(status):
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
        if invalid:
            return await reject(400)
        if declared is not None and declared > limit:
            return await reject(413)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                return await reject(413)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if declared is not None and len(body) != declared:
            return await reject(400)
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        return await self.app(scope, replay, send)
