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
        db.execute("PRAGMA user_version=4")
    with pytest.raises(RuntimeError,match="Unsupported"):
        AuthStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4

def test_code_lookup(store):
    txn,code = pending(store)
    assert store.resolve_pending_code(code,now=1001) == txn
    with pytest.raises(ValueError):
        store.resolve_pending_code("not-a-code",now=1001)

def test_platform_binding(store):
    store.create_profile("owner","chatgpt")
    txn,_ = pending(store)
    assert not store.approve(txn,"owner/chatgpt",now=1001)


def test_fresh_schema_v3(tmp_path):
    store = AuthStore(tmp_path / "fresh.sqlite3")
    with store.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
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
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
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
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert [r[1] for r in db.execute("PRAGMA table_info(connections)")].count("scope") == 1


def test_pending_scopes_resolved_and_visible(store):
    txn, _ = store.create_pending("client1", CALLBACK, "state", "challenge", scopes=None, now=1000)
    row = store.pending(now=1001)[0]
    assert row["txn_id"] == txn
    assert row["scopes"] == "roundtable.append"
    with store.connect() as db:
        assert db.execute("SELECT scopes FROM pending_txns WHERE txn_id=?", (txn,)).fetchone()[0] == "roundtable.append"


@pytest.mark.parametrize("scopes", ["vault.read", "roundtable.append vault.read", "", " ", 123])
def test_pending_rejects_invalid_scopes(store, scopes):
    with pytest.raises(ValueError, match="scopes"):
        store.create_pending("client1", CALLBACK, "state", "challenge", scopes=scopes, now=1000)
    assert store.pending(now=1001) == []


@pytest.mark.parametrize("column,value", [
    ("scope", None),
    ("scope", "vault.read"),
    ("token_endpoint_auth_method", None),
    ("grant_types", "[]"),
    ("response_types", "[]"),
])
def test_pending_rejects_invalid_registered_client(store, column, value):
    with store.connect() as db:
        db.execute(f"UPDATE connections SET {column}=? WHERE client_id='client1'", (value,))
    assert store.get_registered_client("client1", now=1000) is None
    with pytest.raises(ValueError, match="Invalid client"):
        pending(store)


def test_pending_rejects_revoked_bound_profile(store):
    txn, _ = pending(store)
    assert store.approve(txn, "owner/claude", now=1001)
    with store.connect() as db:
        db.execute("UPDATE profiles SET revoked_at=1002 WHERE profile_id='owner/claude'")
    assert store.get_registered_client("client1", now=1003) is None
    with pytest.raises(ValueError, match="Invalid client"):
        pending(store, now=1003)


def test_db_refuses_secretless_secret_post_update(store):
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE connections SET client_secret=NULL WHERE client_id='client1'")
    assert store.get_registered_client("client1", now=1000) is not None


def test_pending_accepts_sdk_scope_list(store):
    txn, _ = store.create_pending("client1", CALLBACK, "state", "challenge",
                                  scopes=["roundtable.append"], now=1000)
    assert store.pending(now=1001)[0]["scopes"] == "roundtable.append"
    assert store.pending(now=1001)[0]["txn_id"] == txn


def test_pending_rejects_sdk_scope_list_escalation(store):
    with pytest.raises(ValueError, match="scopes"):
        store.create_pending("client1", CALLBACK, "state", "challenge",
                             scopes=["roundtable.append", "vault.read"], now=1000)


def test_fresh_v3_pending_resource_columns(tmp_path):
    store = AuthStore(tmp_path / "v3.sqlite3")
    with store.connect() as db:
        columns = {r[1] for r in db.execute("PRAGMA table_info(pending_txns)")}
        assert {"resource", "redirect_uri_provided_explicitly"}.issubset(columns)


def test_v2_pending_row_migrates_with_null_resource(tmp_path):
    path = tmp_path / "v2pending.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE connections (client_id TEXT PRIMARY KEY)")
        db.execute("""CREATE TABLE pending_txns (
            txn_id TEXT PRIMARY KEY, client_id TEXT, match_code TEXT,
            redirect_uri TEXT, state TEXT, code_challenge TEXT, scopes TEXT,
            created_at INTEGER, expires_at INTEGER, status TEXT,
            approved_profile TEXT)""")
        db.execute("INSERT INTO connections(client_id) VALUES ('legacy')")
        db.execute("""INSERT INTO pending_txns
            (txn_id,client_id,match_code,redirect_uri,state,code_challenge,
             scopes,created_at,expires_at,status)
            VALUES ('oldtxn','legacy','1234',?,'state','challenge',
                    'roundtable.append',1000,1180,'approved')""", (CALLBACK,))
        db.execute("PRAGMA user_version=2")
    store = AuthStore(path)
    with store.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        row = db.execute("""SELECT resource,redirect_uri_provided_explicitly,status
                            FROM pending_txns WHERE txn_id='oldtxn'""").fetchone()
        assert row["resource"] is None
        assert row["redirect_uri_provided_explicitly"] is None
        assert row["status"] == "approved"
        assert db.execute("SELECT count(*) FROM auth_codes").fetchone()[0] == 0


CANONICAL_RESOURCE = "https://roundtable.rodsrcpark.com/mcp"


@pytest.mark.parametrize("resource", [None, CANONICAL_RESOURCE])
@pytest.mark.parametrize("explicit", [True, False])
def test_pending_canonical_resource_and_explicit_flag(store, resource, explicit):
    txn, _ = store.create_pending("client1", CALLBACK, "state", "challenge",
                                  resource=resource,
                                  redirect_uri_provided_explicitly=explicit, now=1000)
    with store.connect() as db:
        row = db.execute("""SELECT resource,redirect_uri_provided_explicitly
                            FROM pending_txns WHERE txn_id=?""", (txn,)).fetchone()
    assert row["resource"] == CANONICAL_RESOURCE
    assert row["redirect_uri_provided_explicitly"] == int(explicit)


@pytest.mark.parametrize("resource", [
    "https://other.example/mcp",
    "https://roundtable.rodsrcpark.com/mcp/",
    "",
    "https://roundtable.rodsrcpark.com",
])
def test_pending_rejects_noncanonical_resource(store, resource):
    with pytest.raises(ValueError, match="resource"):
        store.create_pending("client1", CALLBACK, "state", "challenge",
                             resource=resource, now=1000)
    assert store.pending(now=1001) == []


@pytest.mark.parametrize("flag", [None, 0, 1, "true"])
def test_pending_rejects_invalid_redirect_flag(store, flag):
    with pytest.raises(ValueError, match="flag"):
        store.create_pending("client1", CALLBACK, "state", "challenge",
                             redirect_uri_provided_explicitly=flag, now=1000)
    assert store.pending(now=1001) == []


def test_default_pending_lifetime_25_minutes(store):
    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", "A" * 43, now=1000
    )
    with store.connect() as db:
        row = db.execute(
            "SELECT created_at, expires_at FROM pending_txns WHERE txn_id=?",
            (txn,),
        ).fetchone()
    assert row["created_at"] == 1000
    assert row["expires_at"] == 2500
    assert any(item["txn_id"] == txn for item in store.pending(now=2499))
    assert not any(item["txn_id"] == txn for item in store.pending(now=2500))
    assert not store.approve(txn, "owner/claude", now=2500)


def test_only_one_auth_code_per_transaction(store):
    txn, _ = pending(store)
    with store.connect() as db:
        db.execute(
            "INSERT INTO auth_codes(code_hash,txn_id,expires_at) VALUES(?,?,?)",
            (digest("first-code"), txn, 1600),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO auth_codes(code_hash,txn_id,expires_at) VALUES(?,?,?)",
                (digest("second-code"), txn, 1600),
            )


def test_existing_duplicate_auth_codes_fail_migration(store):
    txn, _ = pending(store)
    with store.connect() as db:
        db.execute("DROP INDEX ux_auth_codes_txn_id")
        for value in ("first", "second"):
            db.execute(
                "INSERT INTO auth_codes(code_hash,txn_id,expires_at) VALUES(?,?,?)",
                (digest(value), txn, 1600),
            )

    with pytest.raises(sqlite3.IntegrityError):
        AuthStore(store.path)

    with sqlite3.connect(store.path) as db:
        assert db.execute(
            "SELECT count(*) FROM auth_codes WHERE txn_id=?", (txn,)
        ).fetchone()[0] == 2


def test_issue_auth_code_after_approval(store):
    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", "A" * 43, now=1000
    )
    assert store.issue_auth_code(txn, now=1001) is None
    assert store.approve(txn, "owner/claude", now=1002)

    code = store.issue_auth_code(txn, now=1003)
    assert isinstance(code, str) and len(code) >= 32

    with store.connect() as db:
        row = db.execute(
            "SELECT code_hash,expires_at,used_at FROM auth_codes WHERE txn_id=?",
            (txn,),
        ).fetchone()

    assert row["code_hash"] == digest(code)
    assert row["code_hash"] != code
    assert row["expires_at"] == 1543
    assert row["used_at"] is None
    assert store.issue_auth_code(txn, now=1004) is None


def test_issue_auth_code_rejects_expired_approval(store):
    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", "A" * 43, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)
    assert store.issue_auth_code(txn, now=2499) is not None

    txn2, _ = store.create_pending(
        "client1", CALLBACK, "state2", "A" * 43, now=3000
    )
    assert store.approve(txn2, "owner/claude", now=3001)
    assert store.issue_auth_code(txn2, now=4500) is None


@pytest.mark.parametrize("target", ["connection", "profile"])
def test_issue_auth_code_rejects_revocation(store, target):
    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", "A" * 43, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    if target == "connection":
        assert store.revoke_connection("client1", now=1002)
    else:
        assert store.revoke_profile("owner/claude", now=1002)

    assert store.issue_auth_code(txn, now=1003) is None


def test_issue_auth_code_once_under_concurrency(store):
    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", "A" * 43, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: store.issue_auth_code(txn, now=1002),
                range(2),
            )
        )

    codes = [code for code in results if code is not None]
    assert len(codes) == 1

    with store.connect() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM auth_codes WHERE txn_id=?",
            (txn,),
        ).fetchone()[0]

    assert count == 1
    assert digest(codes[0]) != codes[0]














def test_issue_auth_code_rejects_legacy_null_redirect_flag(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    with store.connect() as db:
        db.execute("""
            UPDATE pending_txns
            SET redirect_uri_provided_explicitly = NULL
            WHERE txn_id = ?
        """, (txn,))

    assert store.issue_auth_code(txn, now=1002) is None

    with store.connect() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM auth_codes WHERE txn_id=?",
            (txn,),
        ).fetchone()[0]

    assert count == 0


def test_load_auth_code_twice_is_read_only(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    first = store.load_auth_code(code, "client1", now=1003)
    second = store.load_auth_code(code, "client1", now=1003)

    assert first is not None
    assert first == second
    assert first["redirect_uri_provided_explicitly"] is True

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id = a.txn_id
            WHERE t.txn_id = ?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def test_consume_auth_code_success_and_replay(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    loaded = store.load_auth_code(code, "client1", now=1003)
    assert loaded is not None

    consumed = store.consume_auth_code(code, "client1", now=1004)
    assert consumed == loaded

    assert store.load_auth_code(code, "client1", now=1005) is None
    assert store.consume_auth_code(code, "client1", now=1005) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id = a.txn_id
            WHERE t.txn_id = ?
        """, (txn,)).fetchone()

    assert record["used_at"] == 1004
    assert record["status"] == "consumed"


def test_consume_auth_code_rechecks_revocation_after_load(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None
    assert store.load_auth_code(code, "client1", now=1003) is not None

    with store.connect() as db:
        db.execute(
            "UPDATE connections SET revoked_at=? WHERE client_id=?",
            (1004, "client1"),
        )

    assert store.consume_auth_code(code, "client1", now=1005) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def test_consume_auth_code_concurrent_only_one_succeeds(store):
    import base64
    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=10)
        return store.consume_auth_code(code, "client1", now=1003)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]

    assert sum(result is not None for result in results) == 1

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] == 1003
    assert record["status"] == "consumed"


def test_consume_auth_code_unknown_and_expired(store):
    import base64
    import hashlib

    assert store.consume_auth_code(
        "unknown-authorization-code", "client1", now=1003
    ) is None

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    # Code lifetime: 540 seconds from issuance.
    assert store.consume_auth_code(
        code, "client1", now=1542
    ) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def test_load_and_consume_auth_code_540_second_boundary(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    def make_code(start):
        txn, _ = store.create_pending(
            "client1", CALLBACK, "state", challenge, now=start
        )
        assert store.approve(txn, "owner/claude", now=start + 1)
        code = store.issue_auth_code(txn, now=start + 2)
        assert code is not None
        return code

    # Issued at 1002; expires at 1542.
    valid_code = make_code(1000)
    assert store.load_auth_code(valid_code, "client1", now=1541) is not None
    assert store.consume_auth_code(valid_code, "client1", now=1541) is not None
    assert store.load_auth_code(valid_code, "client1", now=1542) is None
    assert store.consume_auth_code(valid_code, "client1", now=1543) is None

    expired_code = make_code(1000)
    assert store.load_auth_code(expired_code, "client1", now=1542) is None
    assert store.consume_auth_code(expired_code, "client1", now=1542) is None
    assert store.load_auth_code(expired_code, "client1", now=1543) is None
    assert store.consume_auth_code(expired_code, "client1", now=1543) is None


@pytest.mark.parametrize("trigger_action", ["IGNORE", "ABORT"])
def test_consume_auth_code_rolls_back_if_transaction_update_fails(store, trigger_action):
    import base64
    import hashlib
    import sqlite3
    import pytest

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    error_message = (
        "" if trigger_action == "IGNORE"
        else ", 'simulated transaction failure'"
    )

    with store.connect() as db:
        db.execute(f"""
            CREATE TRIGGER reject_consume_transaction
            BEFORE UPDATE OF status ON pending_txns
            WHEN NEW.status = 'consumed'
            BEGIN
                SELECT RAISE({trigger_action}{error_message});
            END
        """)

    with pytest.raises(sqlite3.IntegrityError):
        store.consume_auth_code(code, "client1", now=1003)

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id = a.txn_id
            WHERE t.txn_id = ?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def test_load_and_consume_reject_legacy_null_redirect_flag(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    # Issue while the flag is valid, then simulate a legacy NULL row.
    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    with store.connect() as db:
        db.execute("""
            UPDATE pending_txns
            SET redirect_uri_provided_explicitly=NULL
            WHERE txn_id=?
        """, (txn,))

    assert store.load_auth_code(code, "client1", now=1003) is None
    assert store.consume_auth_code(code, "client1", now=1003) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def sdk_exchange(store, code, client_id, redirect_uri, verifier, now):
    """Test-only simulation of SDK validation before code consumption."""
    import base64
    import hashlib

    loaded = store.load_auth_code(code, client_id, now=now)
    if loaded is None:
        return None

    expected_redirect = (
        loaded["redirect_uri"]
        if loaded["redirect_uri_provided_explicitly"]
        else None
    )
    if (str(redirect_uri) if redirect_uri is not None else None) != (
        str(expected_redirect) if expected_redirect is not None else None
    ):
        return None

    if not isinstance(verifier, str):
        return None

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    if challenge != loaded["code_challenge"]:
        return None

    return store.consume_auth_code(code, client_id, now=now)


def test_sdk_exchange_redirect_flag_true_and_false(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    def make_code(explicit):
        txn, _ = store.create_pending(
            "client1", CALLBACK, "state", challenge,
            now=1000,
            redirect_uri_provided_explicitly=explicit,
        )
        assert store.approve(txn, "owner/claude", now=1001)
        code = store.issue_auth_code(txn, now=1002)
        assert code is not None
        return txn, code

    # Explicit redirect: missing or incorrect URI must fail.
    explicit_txn, explicit_code = make_code(True)
    assert store.load_auth_code(
        explicit_code, "client1", now=1003
    )["redirect_uri_provided_explicitly"] is True

    assert sdk_exchange(
        store, explicit_code, "client1", None, verifier, 1003
    ) is None
    assert sdk_exchange(
        store, explicit_code, "client1",
        "https://wrong.example/callback", verifier, 1003
    ) is None
    assert sdk_exchange(
        store, explicit_code, "client1", CALLBACK,
        "W" * 43, 1003
    ) is None

    with store.connect() as db:
        row = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (explicit_txn,)).fetchone()
    assert row["used_at"] is None
    assert row["status"] == "approved"

    assert sdk_exchange(
        store, explicit_code, "client1", CALLBACK, verifier, 1004
    ) is not None

    # Implicit redirect: SDK need not receive redirect_uri again.
    implicit_txn, implicit_code = make_code(False)
    assert store.load_auth_code(
        implicit_code, "client1", now=1003
    )["redirect_uri_provided_explicitly"] is False

    assert sdk_exchange(
        store, implicit_code, "client1", CALLBACK, verifier, 1003
    ) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (implicit_txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"

    assert sdk_exchange(
        store, implicit_code, "client1", None, verifier, 1004
    ) is not None

    with store.connect() as db:
        row = db.execute(
            "SELECT status FROM pending_txns WHERE txn_id=?",
            (implicit_txn,),
        ).fetchone()
    assert row["status"] == "consumed"


def test_load_and_consume_reject_wrong_client_without_consuming(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    assert store.load_auth_code(
        code, "wrong-client", now=1003
    ) is None

    assert store.consume_auth_code(
        code, "wrong-client", now=1003
    ) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"

    # A rejected attempt must not invalidate the legitimate client.
    assert store.load_auth_code(
        code, "client1", now=1004
    ) is not None


@pytest.mark.parametrize("target", ["connection", "profile"])
def test_load_and_consume_reject_real_revocation_methods(store, target):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None
    assert store.load_auth_code(code, "client1", now=1003) is not None

    if target == "connection":
        assert store.revoke_connection("client1", now=1004)
    else:
        assert store.revoke_profile("owner/claude", now=1004)

    assert store.load_auth_code(code, "client1", now=1005) is None
    assert store.consume_auth_code(code, "client1", now=1005) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"


def test_load_and_consume_reject_noncanonical_resource(store):
    import base64
    import hashlib

    verifier = "V" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    txn, _ = store.create_pending(
        "client1", CALLBACK, "state", challenge, now=1000
    )
    assert store.approve(txn, "owner/claude", now=1001)

    code = store.issue_auth_code(txn, now=1002)
    assert code is not None

    # Simulate a stored code linked to a noncanonical resource.
    with store.connect() as db:
        db.execute("""
            UPDATE pending_txns
            SET resource=?
            WHERE txn_id=?
        """, ("https://wrong.example/mcp", txn))

    assert store.load_auth_code(code, "client1", now=1003) is None
    assert store.consume_auth_code(code, "client1", now=1003) is None

    with store.connect() as db:
        record = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id=a.txn_id
            WHERE t.txn_id=?
        """, (txn,)).fetchone()

    assert record["used_at"] is None
    assert record["status"] == "approved"
