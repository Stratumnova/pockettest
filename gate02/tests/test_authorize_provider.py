"""C3 authorize-only contract tests. No server or network."""
import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit
import pytest
from mcp.server.auth.provider import AuthorizeError
from auth_store import AuthStore, CANONICAL_RESOURCE
from authorize_provider import C3AuthorizeProvider

CALLBACK = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture
def adapter(tmp_path):
    store = AuthStore(tmp_path / "authorize.sqlite3")
    store.register_connection(
        "sdk-client", "claude", "Claude", CALLBACK, ttl=900,
        client_secret="secret", auth_method="client_secret_post",
        grant_types='["authorization_code","refresh_token"]',
        response_types='["code"]', scope="roundtable.append",
    )
    return C3AuthorizeProvider(store)


def params(**changes):
    values = dict(
        redirect_uri=CALLBACK, state="opaque-state",
        code_challenge="A" * 43, scopes=["roundtable.append"],
        resource=None, redirect_uri_provided_explicitly=True,
    )
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("explicit", [True, False])
def test_authorize_preserves_sdk_flag_and_returns_safe_url(adapter, explicit):
    url = asyncio.run(adapter.authorize(
        SimpleNamespace(client_id="sdk-client"),
        params(redirect_uri_provided_explicitly=explicit),
    ))
    parsed = urlsplit(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "roundtable.rodsrcpark.com"
    assert parsed.path.startswith("/consent/")
    assert parsed.query == ""
    assert "opaque-state" not in url
    with adapter.auth_store.connect() as db:
        row = db.execute("SELECT * FROM pending_txns").fetchone()
    assert row["redirect_uri_provided_explicitly"] == int(explicit)
    assert row["resource"] == CANONICAL_RESOURCE
    assert row["redirect_uri"] == CALLBACK
    assert row["state"] == "opaque-state"
    assert row["code_challenge"] == "A" * 43
    assert row["match_code"] not in url


@pytest.mark.parametrize("state", [None, ""])
def test_missing_or_empty_state_rejected(adapter, state):
    with pytest.raises(AuthorizeError):
        asyncio.run(adapter.authorize(SimpleNamespace(client_id="sdk-client"), params(state=state)))
    assert adapter.auth_store.pending() == []


@pytest.mark.parametrize("resource", ["https://evil.example/mcp", CANONICAL_RESOURCE + "/"])
def test_foreign_or_near_miss_resource_rejected(adapter, resource):
    with pytest.raises(AuthorizeError):
        asyncio.run(adapter.authorize(SimpleNamespace(client_id="sdk-client"), params(resource=resource)))
    assert adapter.auth_store.pending() == []


def test_callback_mismatch_rejected(adapter):
    with pytest.raises(AuthorizeError):
        asyncio.run(adapter.authorize(SimpleNamespace(client_id="sdk-client"), params(redirect_uri="https://evil.example/cb")))
    assert adapter.auth_store.pending() == []


def test_redirect_uri_string_conversion(adapter):
    class URI:
        def __str__(self):
            return CALLBACK
    url = asyncio.run(adapter.authorize(SimpleNamespace(client_id="sdk-client"), params(redirect_uri=URI())))
    assert url.startswith("https://roundtable.rodsrcpark.com/consent/")


def test_absent_state_attribute_rejected(adapter):
    p = params()
    del p.state
    with pytest.raises(AuthorizeError):
        asyncio.run(adapter.authorize(SimpleNamespace(client_id="sdk-client"), p))
    assert adapter.auth_store.pending() == []


@pytest.mark.parametrize("challenge", ["", "A" * 42, "A" * 44, "+" + "A" * 42, "/" + "A" * 42])
def test_invalid_pkce_challenge_rejected(adapter, challenge):
    with pytest.raises(AuthorizeError):
        asyncio.run(adapter.authorize(
            SimpleNamespace(client_id="sdk-client"), params(code_challenge=challenge)))
    assert adapter.auth_store.pending() == []


def test_valid_pkce_challenge_accepted(adapter):
    url = asyncio.run(adapter.authorize(
        SimpleNamespace(client_id="sdk-client"), params(code_challenge="aZ09_-" + "A" * 37)))
    assert url.startswith("https://roundtable.rodsrcpark.com/consent/")
