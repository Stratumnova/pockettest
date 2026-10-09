"""Gate-02A C2: offline dynamic-client-registration policy.

This module is NOT mounted in server.py. Public DCR stays disabled.
Client metadata is untrusted; callback allowlisting does not prove identity.
"""
import secrets
import time
from auth_store import callback_platform

ALLOWED_GRANTS = frozenset(("authorization_code", "refresh_token"))
ALLOWED_RESPONSES = frozenset(("code",))
ALLOWED_AUTH_METHODS = frozenset(("client_secret_post", "none"))
MAX_NAME_LENGTH = 120

class RegistrationError(ValueError):
    pass

def _strings(value, field):
    if not isinstance(value, list) or not value or any(not isinstance(x,str) for x in value):
        raise RegistrationError(f"Invalid {field}")
    if len(value) != len(set(value)):
        raise RegistrationError(f"Duplicate {field}")
    return frozenset(value)

def validate_metadata(metadata):
    if not isinstance(metadata, dict):
        raise RegistrationError("Expected JSON object")
    uris = metadata.get("redirect_uris")
    if not isinstance(uris, list) or len(uris) != 1 or not isinstance(uris[0], str):
        raise RegistrationError("Exactly one redirect URI required")
    try:
        platform = callback_platform(uris[0])
    except ValueError as exc:
        raise RegistrationError("Callback not allowlisted") from exc
    grants = _strings(metadata.get("grant_types", ["authorization_code"]), "grant_types")
    responses = _strings(metadata.get("response_types", ["code"]), "response_types")
    if not grants.issubset(ALLOWED_GRANTS) or "authorization_code" not in grants:
        raise RegistrationError("Unsupported grant type")
    if responses != ALLOWED_RESPONSES:
        raise RegistrationError("Unsupported response type")
    method = metadata.get("token_endpoint_auth_method", "client_secret_post")
    if method not in ALLOWED_AUTH_METHODS:
        raise RegistrationError("Unsupported client auth method")
    name = metadata.get("client_name", platform)
    if not isinstance(name,str) or not (1 <= len(name) <= MAX_NAME_LENGTH):
        raise RegistrationError("Invalid client name")
    # Client name is display-only, never an identity signal.
    for field in ("jwks_uri", "jwks", "software_statement", "sector_identifier_uri"):
        if field in metadata:
            raise RegistrationError(f"Unsupported registration field: {field}")
    return {"platform":platform,"redirect_uri":uris[0],
            "client_name":name,"grant_types":sorted(grants),
            "response_types":["code"],"token_endpoint_auth_method":method}

def register_offline(store, metadata, now=None, ttl=900):
    """Persist unbound client; no network endpoint or issued access tokens."""
    now = int(time.time()) if now is None else int(now)
    if ttl <= 0 or ttl > 900:
        raise RegistrationError("Invalid unbound registration TTL")
    validated = validate_metadata(metadata)
    client_id = secrets.token_urlsafe(32)
    store.register_connection(client_id,validated["platform"],validated["client_name"],
                              validated["redirect_uri"],ttl=ttl,now=now)
    return {"client_id":client_id,"client_id_issued_at":now,
            "client_secret":None,"client_name":validated["client_name"],
            "redirect_uris":[validated["redirect_uri"]],
            "grant_types":validated["grant_types"],
            "response_types":validated["response_types"],
            "token_endpoint_auth_method":validated["token_endpoint_auth_method"]}
