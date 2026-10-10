"""Consent views are local development functions; no public app registration."""
from auth_store import AuthStore
from consent_views import consent_page, consent_status, dev_consent_routes

CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def test_pending_consent_page_and_status(tmp_path):
    store = AuthStore(tmp_path / "views.sqlite3")
    store.register_connection("c", "claude", "Claude", CALLBACK, now=1000,
                              client_secret="secret", auth_method="client_secret_post",
                              grant_types='["authorization_code","refresh_token"]',
                              response_types='["code"]', scope="roundtable.append")
    txn, match = store.create_pending("c", CALLBACK, "secret-state", "A" * 43, now=1000, ttl=180)
    page = consent_page(store, txn, now=1001)
    body = page.body.decode()
    assert page.status_code == 200
    assert match in body
    assert "claude" in body and "roundtable.append" in body
    assert "secret-state" not in body
    assert page.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in page.headers["content-security-policy"]
    status = consent_status(store, txn, now=1001)
    assert status.body == b'{"status":"pending"}'
    assert status.headers["cache-control"] == "no-store"
    assert len(dev_consent_routes(store)) == 2
    assert consent_status(store, txn, now=1180).body == b'{"status":"expired"}'
    assert match not in consent_page(store, txn, now=1180).body.decode()


def test_missing_consent_transaction(tmp_path):
    store = AuthStore(tmp_path / "empty.sqlite3")
    assert consent_page(store, "missing").status_code == 404
    assert consent_status(store, "missing").status_code == 404
