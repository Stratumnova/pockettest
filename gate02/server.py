"""Gate-02A: local-only, deny-all OAuth skeleton.

This is a review candidate, NOT a working authorization server.
Do not connect a public tunnel or grant access to private files.
"""

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
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
from starlette.routing import Route

PUBLIC_ORIGIN = "https://roundtable.rodsrcpark.com"
RESOURCE_URL = PUBLIC_ORIGIN + "/mcp"


class DenyAllProvider(OAuthAuthorizationServerProvider):
    """Fail closed: no clients, authorization codes, or tokens."""

    async def get_client(self, client_id):
        return None

    async def register_client(self, client_info):
        raise ValueError("Client registration disabled in Gate-02A")

    async def authorize(self, client, params):
        raise ValueError("Authorization disabled in Gate-02A")

    async def load_authorization_code(self, client, authorization_code):
        return None

    async def exchange_authorization_code(self, client, authorization_code):
        raise ValueError("Authorization-code exchange disabled")

    async def load_refresh_token(self, client, refresh_token):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raise ValueError("Refresh-token exchange disabled")

    async def load_access_token(self, token):
        return None

    async def revoke_token(self, token):
        return None


provider = DenyAllProvider()
mcp = FastMCP(
    "Pocket Gate-02A (deny-all)",
    auth_server_provider=provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(PUBLIC_ORIGIN),
        resource_server_url=AnyHttpUrl(RESOURCE_URL),
        client_registration_options=ClientRegistrationOptions(enabled=False),
        revocation_options=RevocationOptions(enabled=True),
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
            "roundtable.rodsrcpark.com",
        ],
        allowed_origins=[PUBLIC_ORIGIN],
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
)


async def health(request: Request):
    return JSONResponse({"status": "gate02a-deny-all", "ready": False})


app = mcp.streamable_http_app()
app.routes.append(Route("/health", health, methods=["GET"]))


if __name__ == "__main__":
    # Inspection only. Do not start the server by running this file.
    for route in app.routes:
        print(getattr(route, "path", "<mount>"))
