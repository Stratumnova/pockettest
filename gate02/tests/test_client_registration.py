"""C2 offline DCR policy tests. No server or tunnel."""
import pytest
from auth_store import AuthStore
from client_registration import RegistrationError, register_offline, validate_metadata

CLAUDE="https://claude.ai/api/mcp/auth_callback"
CHATGPT="https://chatgpt.com/connector/oauth/2K3bAoaL_ejV"

@pytest.fixture
def store(tmp_path):
    return AuthStore(tmp_path/"auth.sqlite3")

@pytest.mark.parametrize("callback,platform",[(CLAUDE,"claude"),(CHATGPT,"chatgpt")])
def test_valid_clients_unbound(store,callback,platform):
    metadata={"redirect_uris":[callback],"grant_types":["authorization_code","refresh_token"],
              "response_types":["code"],"token_endpoint_auth_method":"client_secret_post",
              "client_name":"Untrusted Display Name"}
    result=register_offline(store,metadata,now=1000)
    with store.connect() as db:
        row=db.execute("SELECT * FROM connections WHERE client_id=?",(result["client_id"],)).fetchone()
        assert row["profile_id"] is None
        assert row["platform_hint"] == platform
        assert row["expires_at"] == 1900
        assert db.execute("SELECT count(*) FROM project_grants").fetchone()[0] == 0
    assert result["client_secret"] is None

@pytest.mark.parametrize("uri",[
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
def test_reject_bad_callbacks(uri):
    with pytest.raises(RegistrationError):
        validate_metadata({"redirect_uris":[uri]})

def test_reject_multiple_callbacks():
    with pytest.raises(RegistrationError):
        validate_metadata({"redirect_uris":[CLAUDE,CHATGPT]})

@pytest.mark.parametrize("metadata",[
    {"redirect_uris":[CLAUDE],"grant_types":["client_credentials"]},
    {"redirect_uris":[CLAUDE],"response_types":["token"]},
    {"redirect_uris":[CLAUDE],"token_endpoint_auth_method":"client_secret_basic"},
    {"redirect_uris":[CLAUDE],"jwks_uri":"https://example.com/keys"},
    {"redirect_uris":[CLAUDE],"grant_types":["authorization_code","authorization_code"]},
    {"redirect_uris":[CLAUDE],"client_name":""},
    {"redirect_uris":[CLAUDE],"client_name":"x"*121},
])
def test_reject_invalid_metadata(metadata):
    with pytest.raises(RegistrationError):
        validate_metadata(metadata)

def test_expired_unbound_registration(store):
    r=register_offline(store,{"redirect_uris":[CLAUDE]},now=1000)
    with pytest.raises(ValueError):
        store.create_pending(r["client_id"],CLAUDE,"s","pkce",now=1900)

def test_registration_never_binds_profile(store):
    store.create_profile("owner","claude")
    r=register_offline(store,{"redirect_uris":[CLAUDE],"client_name":"ChatGPT"},now=1000)
    with store.connect() as db:
        row=db.execute("SELECT profile_id,platform_hint FROM connections WHERE client_id=?",(r["client_id"],)).fetchone()
        assert row["profile_id"] is None and row["platform_hint"]=="claude"
