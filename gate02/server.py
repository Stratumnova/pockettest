"""Gate-02A: deny-all OAuth baseline with opt-in isolated loopback read test mode.

Anonymous local mode must never be exposed through a public tunnel or proxy.
"""

import base64
import hashlib
import os
import stat

from mcp.server.auth.provider import (OAuthAuthorizationServerProvider, RegistrationError, AuthorizeError, TokenError)
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse
from listening_wall import BodyLimitMiddleware

PUBLIC_ORIGIN = "https://roundtable.rodsrcpark.com"
RESOURCE_URL = PUBLIC_ORIGIN + "/mcp"
MAX_SHARED_BYTES = 1_048_576
LOCAL_READ_MODE = os.environ.get("A25_LOCAL_READ_MODE") == "1"
SHARED_FILE = os.environ.get("A25_SHARED_READ_FILE")


def read_fixed_file(path):
    """Read only the configured absolute regular-file path."""
    if not path or not os.path.isabs(path):
        return {"error": "shared_file_unavailable"}
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SHARED_BYTES:
                return {"error": "shared_file_unavailable"}
            with os.fdopen(fd, "rb", closefd=False) as stream:
                payload = stream.read(MAX_SHARED_BYTES + 1)
            if len(payload) > MAX_SHARED_BYTES:
                return {"error": "shared_file_unavailable"}
            return {"encoding": "base64",
                    "content_base64": base64.b64encode(payload).decode("ascii"),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "byte_length": len(payload)}
        finally:
            os.close(fd)
    except (OSError, ValueError):
        return {"error": "shared_file_unavailable"}


FORWARDED_HEADERS = frozenset({
    b"cf-connecting-ip", b"cf-ray", b"x-forwarded-for",
    b"forwarded", b"x-real-ip",
})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


class LoopbackOnly:
    """Deny anonymous test-mode requests unless peer is loopback."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            peer = scope.get("client")
            headers = scope.get("headers", [])
            host_values = [value.decode("ascii", "ignore").lower().strip()
                           for name, value in headers if name.lower() == b"host"]
            safe_host = (len(host_values) == 1 and
                         host_values[0].split(":")[0] in LOCAL_HOSTS)
            # Bracketed IPv6 hosts require special handling, not a naive split.
            if len(host_values) == 1 and host_values[0].startswith("[::1]"):
                safe_host = host_values[0] == "[::1]" or host_values[0].startswith("[::1]:")
            unsafe_forwarding = any(name.lower() in FORWARDED_HEADERS for name, _ in headers)
            if (not peer or peer[0] not in ("127.0.0.1", "::1")
                    or not safe_host or unsafe_forwarding):
                if scope["type"] == "http":
                    await send({"type": "http.response.start", "status": 403,
                                "headers": [(b"content-length", b"0")]})
                    await send({"type": "http.response.body", "body": b""})
                else:
                    await send({"type": "websocket.close", "code": 1008})
                return
        await self.app(scope, receive, send)



class DenyAllProvider(OAuthAuthorizationServerProvider):
    """Fail closed: no clients, authorization codes, or tokens."""

    async def get_client(self, client_id):
        return None

    async def register_client(self, client_info):
        raise RegistrationError(error="invalid_client_metadata", error_description="Registration disabled in Gate-02A")

    async def authorize(self, client, params):
        raise AuthorizeError(error="access_denied", error_description="Authorization disabled in Gate-02A")

    async def load_authorization_code(self, client, authorization_code):
        return None

    async def exchange_authorization_code(self, client, authorization_code):
        raise TokenError(error="invalid_grant", error_description="Authorization-code exchange disabled")

    async def load_refresh_token(self, client, refresh_token):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raise TokenError(error="invalid_grant", error_description="Refresh-token exchange disabled")

    async def load_access_token(self, token):
        return None

    async def revoke_token(self, token):
        return None


provider = DenyAllProvider()
auth_settings = None if LOCAL_READ_MODE else AuthSettings(
    issuer_url=AnyHttpUrl(PUBLIC_ORIGIN),
    resource_server_url=AnyHttpUrl(RESOURCE_URL),
    client_registration_options=ClientRegistrationOptions(enabled=False),
    revocation_options=RevocationOptions(enabled=True),
)
mcp = FastMCP(
    "Pocket Gate-02A (local read)" if LOCAL_READ_MODE else "Pocket Gate-02A (deny-all)",
    auth_server_provider=None if LOCAL_READ_MODE else provider,
    auth=auth_settings,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
            *( [] if LOCAL_READ_MODE else ["roundtable.rodsrcpark.com"] ),
        ],
        allowed_origins=[PUBLIC_ORIGIN],
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
)


@mcp.tool()
def read_shared_file() -> dict:
    """Lossless content and integrity receipt for one configured file."""
    return read_fixed_file(SHARED_FILE)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    return JSONResponse({"status": "gate02a-local-read" if LOCAL_READ_MODE else "gate02a-deny-all", "ready": False})


starlette_app = mcp.streamable_http_app()
app = BodyLimitMiddleware(starlette_app)
if LOCAL_READ_MODE:
    app = LoopbackOnly(app)


if __name__ == "__main__":
    # Inspection only. Do not start the server by running this file.
    for route in starlette_app.routes:
        print(getattr(route, "path", "<mount>"))
