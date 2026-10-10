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


def test_redeem_auth_code_success_and_replay(store):
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

    result = store.redeem_auth_code(
        code, "client1", CALLBACK, verifier,
        "https://roundtable.rodsrcpark.com/mcp", now=1003
    )

    assert result == {
        "client_id": "client1",
        "scopes": "roundtable.append",
        "resource": "https://roundtable.rodsrcpark.com/mcp",
        "txn_id": txn,
    }

    assert store.redeem_auth_code(
        code, "client1", CALLBACK, verifier,
        "https://roundtable.rodsrcpark.com/mcp", now=1004
    ) is None

    with store.connect() as db:
        used = db.execute(
            "SELECT used_at FROM auth_codes WHERE txn_id=?", (txn,)
        ).fetchone()[0]
        status = db.execute(
            "SELECT status FROM pending_txns WHERE txn_id=?", (txn,)
        ).fetchone()[0]

    assert used == 1003
    assert status == "consumed"


@pytest.mark.parametrize("invalid_field", [
    "verifier", "client", "callback", "resource"
])
def test_redeem_auth_code_rejects_mismatch_without_consuming(store, invalid_field):
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

    args = {
        "code": code,
        "client_id": "client1",
        "redirect_uri": CALLBACK,
        "code_verifier": verifier,
        "resource": "https://roundtable.rodsrcpark.com/mcp",
        "now": 1003,
    }
    changes = {
        "verifier": ("code_verifier", "X" * 43),
        "client": ("client_id", "wrong-client"),
        "callback": ("redirect_uri", "https://wrong.example/callback"),
        "resource": ("resource", "https://wrong.example/mcp"),
    }
    key, value = changes[invalid_field]
    args[key] = value

    assert store.redeem_auth_code(**args) is None

    with store.connect() as db:
        assert db.execute(
            "SELECT used_at FROM auth_codes WHERE txn_id=?", (txn,)
        ).fetchone()[0] is None

    args[key] = {
        "code_verifier": verifier,
        "client_id": "client1",
        "redirect_uri": CALLBACK,
        "resource": "https://roundtable.rodsrcpark.com/mcp",
    }[key]
    assert store.redeem_auth_code(**args) is not None


@pytest.mark.parametrize("redeem_at,expected_success", [
    (1541, True),
    (1542, False),
    (1543, False),
])
def test_redeem_auth_code_540_second_boundary(store, redeem_at, expected_success):
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

    result = store.redeem_auth_code(
        code, "client1", CALLBACK, verifier,
        "https://roundtable.rodsrcpark.com/mcp",
        now=redeem_at,
    )
    assert (result is not None) is expected_success


@pytest.mark.parametrize("target", ["connection", "profile"])
def test_redeem_auth_code_rejects_revocation(store, target):
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

    if target == "connection":
        assert store.revoke_connection("client1", now=1003)
    else:
        assert store.revoke_profile("owner/claude", now=1003)

    assert store.redeem_auth_code(
        code, "client1", CALLBACK, verifier,
        "https://roundtable.rodsrcpark.com/mcp", now=1004
    ) is None

    with store.connect() as db:
        assert db.execute(
            "SELECT used_at FROM auth_codes WHERE txn_id=?",
            (txn,),
        ).fetchone()[0] is None


def test_redeem_auth_code_once_under_concurrency(store):
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

    def redeem(_):
        return store.redeem_auth_code(
            code, "client1", CALLBACK, verifier,
            "https://roundtable.rodsrcpark.com/mcp",
            now=1003,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, range(2)))

    assert sum(result is not None for result in results) == 1
    assert sum(result is None for result in results) == 1

    with store.connect() as db:
        row = db.execute(
            "SELECT used_at FROM auth_codes WHERE txn_id=?",
            (txn,),
        ).fetchone()
    assert row["used_at"] == 1003


def test_redeem_auth_code_rolls_back_if_transaction_update_fails(store):
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

    with store.connect() as db:
        db.execute("""
            CREATE TRIGGER block_pending_consumption
            BEFORE UPDATE OF status ON pending_txns
            WHEN NEW.status = 'consumed'
            BEGIN
                SELECT RAISE(IGNORE);
            END
        """)

    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.redeem_auth_code(
            code, "client1", CALLBACK, verifier,
            "https://roundtable.rodsrcpark.com/mcp",
            now=1003,
        )

    with store.connect() as db:
        row = db.execute("""
            SELECT a.used_at, t.status
            FROM auth_codes a
            JOIN pending_txns t ON t.txn_id = a.txn_id
            WHERE t.txn_id = ?
        """, (txn,)).fetchone()

    assert row["used_at"] is None
    assert row["status"] == "approved"
