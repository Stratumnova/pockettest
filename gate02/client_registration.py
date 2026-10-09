"""C2 MCP SDK registration provider mixin; NOT mounted on public server.

The SDK issues client_id/client_secret and calls register_client(client_info).
Owner approval and token issuance remain separate future milestones.
"""
from mcp.shared.auth import OAuthClientInformationFull
from mcp.server.auth.provider import RegistrationError
from auth_store import callback_platform

ALLOWED_GRANTS = frozenset(("authorization_code", "refresh_token"))
MAX_NAME_LENGTH = 120

def validate_client(client):
    """Validate the actual SDK client model, not a parallel metadata format."""
    uris = [str(u) for u in client.redirect_uris]
    if len(uris) != 1:
        raise RegistrationError("invalid_redirect_uri", "Exactly one callback required")
    try:
        platform = callback_platform(uris[0])
    except ValueError as exc:
        raise RegistrationError("invalid_redirect_uri", "Callback not allowlisted") from exc
    if client.token_endpoint_auth_method != "client_secret_post":
        raise RegistrationError("invalid_client_metadata", "Only client_secret_post is supported")
    if not isinstance(client.client_secret, str) or not client.client_secret:
        raise RegistrationError("invalid_client_metadata", "Nonempty client secret required")
    grants = set(client.grant_types or [])
    if grants != ALLOWED_GRANTS:
        raise RegistrationError("invalid_client_metadata", "Expected authorization_code and refresh_token")
    if list(client.response_types or []) != ["code"]:
        raise RegistrationError("invalid_client_metadata", "Expected code response")
    name = client.client_name or platform
    if not isinstance(name, str) or not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise RegistrationError("invalid_client_metadata", "Invalid client name")
    if not client.client_id:
        raise RegistrationError("invalid_client_metadata", "Missing SDK-issued client ID")
    return platform, uris[0], name

class C2ClientRegistration:
    """Mixin for the eventual OAuthAuthorizationServerProvider implementation."""
    def __init__(self, auth_store):
        self.auth_store = auth_store

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        platform, callback, name = validate_client(client_info)
        try:
            self.auth_store.register_connection(
            client_id=client_info.client_id,
            platform_hint=platform, client_name=name, redirect_uri=callback,
            client_secret=client_info.client_secret,
            auth_method="client_secret_post",
            grant_types='["authorization_code","refresh_token"]',
            response_types='["code"]',
            issued_at=client_info.client_id_issued_at,
            ttl=900)
        except ValueError as exc:
            raise RegistrationError("invalid_client_metadata", "Client registration rejected") from exc

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self.auth_store.get_registered_client(client_id)
        if row is None:
            return None
        # Only reconstruct fully authenticated clients; never return missing secrets.
        return OAuthClientInformationFull(
            client_id=row["client_id"],
            client_secret=row["client_secret"],
            client_id_issued_at=row["client_id_issued_at"] or row["created_at"],
            client_secret_expires_at=0,
            redirect_uris=[row["redirect_uri"]],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="client_secret_post",
            client_name=row["client_name"])
