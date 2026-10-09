"""C2 provider-level regression tests, offline."""
import asyncio
import sqlite3
import pytest
from mcp.shared.auth import OAuthClientInformationFull
from auth_store import AuthStore, callback_platform
from client_registration import C2ClientRegistration
from mcp.server.auth.provider import RegistrationError

CLAUDE="https://claude.ai/api/mcp/auth_callback"
CHATGPT="https://chatgpt.com/connector/oauth/2K3bAoaL_ejV"

def client(callback=CLAUDE, **overrides):
    values=dict(client_id="sdk-issued-id", client_secret="sdk-issued-secret",
        redirect_uris=[callback], grant_types=["authorization_code","refresh_token"],
        response_types=["code"], token_endpoint_auth_method="client_secret_post",
        client_name="Untrusted Display Name",client_id_issued_at=1000,
        client_secret_expires_at=0)
    values.update(overrides)
    return OAuthClientInformationFull(**values)

@pytest.fixture
def provider(tmp_path):
    return C2ClientRegistration(AuthStore(tmp_path/"auth.sqlite3"))

@pytest.mark.parametrize("callback,platform",[(CLAUDE,"claude"),(CHATGPT,"chatgpt")])
def test_positive_callbacks(provider,callback,platform):
    assert callback_platform(callback)==platform
    asyncio.run(provider.register_client(client(callback)))
    returned=asyncio.run(provider.get_client("sdk-issued-id"))
    assert returned is not None and returned.client_secret=="sdk-issued-secret"
    with provider.auth_store.connect() as db:
        row=db.execute("SELECT * FROM connections").fetchone()
        assert row["platform_hint"]==platform and row["profile_id"] is None
        assert row["token_endpoint_auth_method"]=="client_secret_post"
        assert row["client_secret"]=="sdk-issued-secret"

@pytest.mark.parametrize("callback",[
    "http://claude.ai/api/mcp/auth_callback",
    "https://claude.ai/api/mcp/auth_callback/",
    "https://claude.ai.evil.com/api/mcp/auth_callback",
    "https://chatgpt.com/connector/oauth/",
    "https://chatgpt.com/connector/oauth/a/b",
    "https://chatgpt.com/connector/oauth/"+"a"*65,
    "https://chatgpt.com/connector/oauth/a?next=evil",
    "https://chatgpt.com/connector/oauth/%2F",
    "https://evil.example/cb",
])
def test_bad_callbacks(provider,callback):
    with pytest.raises(RegistrationError) as err:
        asyncio.run(provider.register_client(client(callback)))
    assert err.value.error == "invalid_redirect_uri"

@pytest.mark.parametrize("override",[
    {"client_secret":None},
    {"client_secret":""},
    {"token_endpoint_auth_method":"none"},
    {"token_endpoint_auth_method":"client_secret_basic"},
    {"grant_types":["authorization_code"]},
    {"response_types":["token"]},
    {"redirect_uris":[CLAUDE,CHATGPT]},
])
def test_reject_bad_sdk_metadata(provider,override):
    with pytest.raises(RegistrationError) as err:
        asyncio.run(provider.register_client(client(**override)))
    assert err.value.error == "invalid_client_metadata"

def test_missing_secret_fails_closed_on_read(provider):
    asyncio.run(provider.register_client(client()))
    with provider.auth_store.connect() as db:
        # Simulate legacy/malformed record with no auth method.
        db.execute("UPDATE connections SET token_endpoint_auth_method=NULL,client_secret=NULL")
    assert asyncio.run(provider.get_client("sdk-issued-id")) is None

def test_revoked_fails_closed(provider):
    asyncio.run(provider.register_client(client()))
    provider.auth_store.revoke_connection("sdk-issued-id")
    assert asyncio.run(provider.get_client("sdk-issued-id")) is None

def test_queue_limit(provider):
    for i in range(5):
        asyncio.run(provider.register_client(client(client_id=f"client-{i}")))
    with pytest.raises(RegistrationError) as err:
        asyncio.run(provider.register_client(client(client_id="sixth")))
    assert err.value.error == "invalid_client_metadata"

def test_sqlite_check_rejects_secretless_secret_post(provider):
    with provider.auth_store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("""INSERT INTO connections
                (client_id,platform_hint,client_name,redirect_uri,created_at,expires_at,
                 token_endpoint_auth_method,client_secret)
                VALUES ('bad','claude','bad',?,1000,2000,'client_secret_post',NULL)""",(CLAUDE,))
