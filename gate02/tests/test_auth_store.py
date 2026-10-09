"""Offline Gate-02A C1 storage tests. No Uvicorn or network required."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from auth_store import AuthStore, digest

CALLBACK = "https://claude.ai/api/mcp/auth_callback"

@pytest.fixture
def store(tmp_path):
    s = AuthStore(tmp_path / "auth.sqlite3")
    s.create_profile("owner","claude")
    s.register_connection("client1","claude","Claude",CALLBACK,now=1000,
        client_secret="fixture-secret",auth_method="client_secret_post",
        grant_types='["authorization_code","refresh_token"]',
        response_types='["code"]',scope="roundtable.append")
    return s

def pending(s, now=1000, ttl=180):
    return s.create_pending("client1",CALLBACK,"state","challenge",now=now,ttl=ttl)

def test_create_approve_and_bind(store):
    txn, number = pending(store)
    assert len(number) == 4 and number.isdigit()
    assert store.pending(now=1001)[0]["txn_id"] == txn
    assert store.approve(txn,"owner/claude",now=1001)
    with store.connect() as db:
        assert db.execute("SELECT profile_id FROM connections WHERE client_id='client1'").fetchone()[0] == "owner/claude"
        assert db.execute("SELECT status FROM pending_txns WHERE txn_id=?",(txn,)).fetchone()[0] == "approved"
    assert not store.approve(txn,"owner/claude",now=1002)

def test_deny_and_expire(store):
    txn,_ = pending(store)
    assert store.deny(txn,now=1001)
    assert not store.approve(txn,"owner/claude",now=1002)
    txn2,_ = pending(store,ttl=1)
    assert store.expire(now=1002) == 1
    assert not store.approve(txn2,"owner/claude",now=1002)

def test_binding_failure_rolls_back(store):
    txn,_ = pending(store)
    assert not store.approve(txn,"missing/profile",now=1001)
    with store.connect() as db:
        assert db.execute("SELECT status FROM pending_txns WHERE txn_id=?",(txn,)).fetchone()[0] == "pending"
        assert db.execute("SELECT profile_id FROM connections WHERE client_id='client1'").fetchone()[0] is None

def test_approve_once_race(store):
    txn,_ = pending(store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:store.approve(txn,"owner/claude",now=1001),range(2)))
    assert sorted(results) == [False,True]

def test_revoke(store):
    txn,_ = pending(store)
    assert store.revoke_connection("client1",now=1001)
    assert not store.approve(txn,"owner/claude",now=1002)
    assert not store.revoke_connection("client1",now=1002)

def test_profile_revoke(store):
    assert store.revoke_profile("owner/claude",now=1001)
    txn,_ = pending(store)
    assert not store.approve(txn,"owner/claude",now=1002)

def test_persistence_backup_and_empty_grants(store,tmp_path):
    txn,_ = pending(store)
    assert store.approve(txn,"owner/claude",now=1001)
    reopened = AuthStore(store.path)
    with reopened.connect() as db:
        assert db.execute("SELECT count(*) FROM project_grants").fetchone()[0] == 0
        assert db.execute("SELECT status FROM pending_txns WHERE txn_id=?",(txn,)).fetchone()[0] == "approved"
    destination = tmp_path / "backup.sqlite3"
    reopened.backup(destination)
    assert AuthStore(destination).pending(now=1001) == []

def test_callback_and_queue_limit(store):
    with pytest.raises(ValueError):
        store.create_pending("client1","https://evil.example/cb","s","c",now=1000)
    for _ in range(5):
        pending(store)
    with pytest.raises(ValueError,match="full"):
        pending(store)

def test_hashes():
    assert digest("secret") != "secret"
    assert len(digest("secret")) == 64

def test_bound_connection_does_not_expire(store):
    txn,_ = pending(store)
    assert store.approve(txn,"owner/claude",now=1001)
    with store.connect() as db:
        assert db.execute("SELECT expires_at FROM connections WHERE client_id='client1'").fetchone()[0] is None
    later,_ = pending(store,now=2000)
    assert store.approve(later,"owner/claude",now=2001)

def test_reject_future_schema_version(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=3")
    with pytest.raises(RuntimeError,match="Unsupported"):
        AuthStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3

def test_code_lookup(store):
    txn,code = pending(store)
    assert store.resolve_pending_code(code,now=1001) == txn
    with pytest.raises(ValueError):
        store.resolve_pending_code("not-a-code",now=1001)

def test_platform_binding(store):
    store.create_profile("owner","chatgpt")
    txn,_ = pending(store)
    assert not store.approve(txn,"owner/chatgpt",now=1001)


def test_fresh_schema_v2(tmp_path):
    store = AuthStore(tmp_path / "fresh.sqlite3")
    with store.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert "scope" in [r[1] for r in db.execute("PRAGMA table_info(connections)")]


def test_v1_migration_preserves_legacy_row(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE connections (
            client_id TEXT PRIMARY KEY, platform_hint TEXT, client_name TEXT,
            redirect_uri TEXT, created_at INTEGER, expires_at INTEGER,
            revoked_at INTEGER, profile_id TEXT, client_secret TEXT,
            token_endpoint_auth_method TEXT, grant_types TEXT,
            response_types TEXT, client_id_issued_at INTEGER)""")
        db.execute("""INSERT INTO connections
            (client_id,platform_hint,client_name,redirect_uri,created_at,expires_at)
            VALUES ('old','claude','Claude',?,1000,1900)""", (CALLBACK,))
        db.execute("PRAGMA user_version=1")
    migrated = AuthStore(path)
    with migrated.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT scope FROM connections WHERE client_id='old'").fetchone()[0] is None
    assert migrated.get_registered_client("old", now=1001) is None


def test_concurrent_v1_migration(tmp_path):
    path = tmp_path / "parallel.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE connections (client_id TEXT PRIMARY KEY)")
        db.execute("PRAGMA user_version=1")
    with ThreadPoolExecutor(max_workers=2) as pool:
        stores = list(pool.map(lambda _: AuthStore(path), range(2)))
    with stores[0].connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert [r[1] for r in db.execute("PRAGMA table_info(connections)")].count("scope") == 1
