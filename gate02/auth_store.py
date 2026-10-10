"""Gate-02A C1: offline SQLite auth state. Not wired into public server."""
import hashlib
import os
import secrets
import sqlite3
import time
import re
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 3
CANONICAL_RESOURCE = "https://roundtable.rodsrcpark.com/mcp"
PLATFORMS = frozenset(("claude", "chatgpt"))
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
CHATGPT_CALLBACK = re.compile(r"\Ahttps://chatgpt\.com/connector/oauth/[A-Za-z0-9_-]{1,64}\Z")


def callback_platform(uri):
    if uri == CLAUDE_CALLBACK:
        return "claude"
    if CHATGPT_CALLBACK.fullmatch(uri):
        return "chatgpt"
    raise ValueError("Callback is not allowlisted")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

class AuthStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _init(self):
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connect() as db:
            for attempt in range(50):
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower():
                        raise
                    if attempt == 49:
                        raise
                    time.sleep(0.1)
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, SCHEMA_VERSION):
                raise RuntimeError(f"Unsupported auth schema version: {version}")
            schema = """
            CREATE TABLE IF NOT EXISTS profiles (
                profile_id TEXT PRIMARY KEY,
                human_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                revoked_at INTEGER,
                UNIQUE(human_id, platform)
            );
            CREATE TABLE IF NOT EXISTS connections (
                client_id TEXT PRIMARY KEY,
                platform_hint TEXT NOT NULL,
                client_name TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                profile_id TEXT REFERENCES profiles(profile_id),
                created_at INTEGER NOT NULL,
                expires_at INTEGER,
                revoked_at INTEGER,
                client_secret TEXT,
                token_endpoint_auth_method TEXT,
                grant_types TEXT,
                response_types TEXT,
                client_id_issued_at INTEGER,
                scope TEXT,
                CHECK(token_endpoint_auth_method IS NULL OR
                      (token_endpoint_auth_method='client_secret_post' AND
                       client_secret IS NOT NULL AND length(client_secret)>0))
            );
            CREATE TABLE IF NOT EXISTS pending_txns (
                txn_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL REFERENCES connections(client_id),
                match_code TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                state TEXT NOT NULL,
                code_challenge TEXT NOT NULL,
                scopes TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','denied','expired','consumed')),
                approved_profile TEXT REFERENCES profiles(profile_id),
                resource TEXT,
                redirect_uri_provided_explicitly INTEGER
            );
            CREATE TABLE IF NOT EXISTS auth_codes (
                code_hash TEXT PRIMARY KEY,
                txn_id TEXT NOT NULL REFERENCES pending_txns(txn_id),
                expires_at INTEGER NOT NULL,
                used_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS access_tokens (
                token_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL REFERENCES connections(client_id),
                resource TEXT NOT NULL,
                scopes TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL REFERENCES connections(client_id),
                scopes TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER,
                revoked_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS project_grants (
                profile_id TEXT NOT NULL REFERENCES profiles(profile_id),
                project_id TEXT NOT NULL,
                can_read INTEGER NOT NULL DEFAULT 0 CHECK(can_read IN (0,1)),
                can_submit INTEGER NOT NULL DEFAULT 0 CHECK(can_submit IN (0,1)),
                PRIMARY KEY(profile_id, project_id)
            );
            CREATE TABLE IF NOT EXISTS revocations (
                revocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL CHECK(target_type IN ('connection','profile')),
                target_id TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
                """
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_auth_codes_txn_id ON auth_codes(txn_id)"
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(connections)")}
            if "scope" not in columns:
                db.execute("ALTER TABLE connections ADD COLUMN scope TEXT")
            pending_columns = {row[1] for row in db.execute("PRAGMA table_info(pending_txns)")}
            if "resource" not in pending_columns:
                db.execute("ALTER TABLE pending_txns ADD COLUMN resource TEXT")
            if "redirect_uri_provided_explicitly" not in pending_columns:
                db.execute("ALTER TABLE pending_txns ADD COLUMN redirect_uri_provided_explicitly INTEGER")
            if version != SCHEMA_VERSION:
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise RuntimeError("Unsupported auth schema")

    def create_profile(self, human_id, platform):
        profile_id = human_id + "/" + platform
        with self.connect() as db:
            db.execute("INSERT INTO profiles(profile_id,human_id,platform) VALUES(?,?,?)",
                       (profile_id, human_id, platform))
        return profile_id

    def register_connection(self, client_id, platform_hint, client_name, redirect_uri,
                            ttl=900, now=None, client_secret=None, auth_method=None,
                            grant_types=None, response_types=None, issued_at=None, scope=None):
        now = int(time.time()) if now is None else int(now)
        if platform_hint not in PLATFORMS or callback_platform(redirect_uri) != platform_hint:
            raise ValueError("Invalid platform or callback")
        if not client_id or ttl <= 0:
            raise ValueError("Invalid registration")
        if auth_method is not None and (auth_method != "client_secret_post" or
                                        not isinstance(client_secret, str) or not client_secret):
            raise ValueError("Secret-based registration requires a nonempty secret")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("""SELECT count(*) FROM connections WHERE profile_id IS NULL
                AND revoked_at IS NULL AND expires_at>?""", (now,)).fetchone()[0]
            if count >= 5:
                raise ValueError("Unbound registration queue full")
            db.execute("""INSERT INTO connections
                (client_id,platform_hint,client_name,redirect_uri,created_at,expires_at,
                 client_secret,token_endpoint_auth_method,grant_types,response_types,client_id_issued_at,scope)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (client_id, platform_hint, client_name, redirect_uri, now, now+ttl,
                 client_secret,auth_method,grant_types,response_types,issued_at,scope))

    @staticmethod
    def _client_row_valid(row, now):
        """One fail-closed check shared by read and pending creation."""
        if row is None or row["revoked_at"] is not None or row["profile_revoked"] is not None:
            return False
        if row["expires_at"] is not None and row["expires_at"] <= now:
            return False
        try:
            if callback_platform(row["redirect_uri"]) != row["platform_hint"]:
                return False
        except (ValueError, TypeError):
            return False
        return (row["token_endpoint_auth_method"] == "client_secret_post"
                and isinstance(row["client_secret"], str) and bool(row["client_secret"])
                and row["grant_types"] == '["authorization_code","refresh_token"]'
                and row["response_types"] == '["code"]'
                and row["scope"] == "roundtable.append")

    def get_registered_client(self, client_id, now=None):
        """Return only well-formed, live, secret-authenticated clients."""
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            row = db.execute("""SELECT c.*,p.revoked_at AS profile_revoked
                FROM connections c LEFT JOIN profiles p ON p.profile_id=c.profile_id
                WHERE c.client_id=?""", (client_id,)).fetchone()
        return dict(row) if self._client_row_valid(row, now) else None

    def create_pending(self, client_id, redirect_uri, state, code_challenge,
                       scopes=None, ttl=1500, now=None, resource=None,
                       redirect_uri_provided_explicitly=True):
        now = int(time.time()) if now is None else int(now)
        if resource is None:
            resource = CANONICAL_RESOURCE
        elif not isinstance(resource, str) or resource != CANONICAL_RESOURCE:
            raise ValueError("Invalid resource")
        if not isinstance(redirect_uri_provided_explicitly, bool):
            raise ValueError("Invalid redirect flag")
        txn_id = secrets.token_urlsafe(32)
        match_code = f"{secrets.randbelow(10000):04d}"
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            client = db.execute("""SELECT c.*,p.revoked_at AS profile_revoked
                FROM connections c LEFT JOIN profiles p ON p.profile_id=c.profile_id
                WHERE c.client_id=?""", (client_id,)).fetchone()
            if not self._client_row_valid(client, now) or client["redirect_uri"] != redirect_uri:
                raise ValueError("Invalid client or callback")
            registered = set(client["scope"].split())
            requested = (registered if scopes is None else
                         set(scopes.split()) if isinstance(scopes, str) else
                         set(scopes) if isinstance(scopes, (list, tuple)) and
                         all(isinstance(item, str) for item in scopes) else set())
            if not requested or not requested.issubset(registered) or not requested.issubset({"roundtable.append"}):
                raise ValueError("Invalid requested scopes")
            resolved_scopes = " ".join(sorted(requested))
            active = db.execute("""SELECT count(*) FROM pending_txns
                WHERE status='pending' AND expires_at>?""", (now,)).fetchone()[0]
            if active >= 5:
                raise ValueError("Pending queue full")
            db.execute("""INSERT INTO pending_txns
                (txn_id,client_id,match_code,redirect_uri,state,code_challenge,
                 scopes,created_at,expires_at,resource,redirect_uri_provided_explicitly)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (txn_id,client_id,match_code,redirect_uri,state,code_challenge,
                 resolved_scopes,now,now+ttl,resource,int(redirect_uri_provided_explicitly)))
        return txn_id, match_code

    def pending(self, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT t.txn_id,t.match_code,t.created_at,t.expires_at,t.scopes,
                       c.platform_hint,c.client_name,c.client_id
                FROM pending_txns t JOIN connections c USING(client_id)
                WHERE t.status='pending' AND t.expires_at>?
                ORDER BY t.created_at,t.txn_id""", (now,))]

    def approve(self, txn_id, profile_id, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            profile = db.execute("SELECT platform FROM profiles WHERE profile_id=? AND revoked_at IS NULL",
                                 (profile_id,)).fetchone()
            if profile is None:
                return False
            txn = db.execute("""SELECT t.client_id,c.profile_id,c.platform_hint,c.revoked_at,
                                      c.expires_at
                FROM pending_txns t JOIN connections c USING(client_id)
                WHERE t.txn_id=?""", (txn_id,)).fetchone()
            if txn is None or txn["revoked_at"] is not None or (txn["expires_at"] is not None and txn["expires_at"] <= now):
                return False
            if txn["platform_hint"] != profile["platform"]:
                return False
            if txn["profile_id"] not in (None, profile_id):
                return False
            updated = db.execute("""UPDATE pending_txns
                SET status='approved',approved_profile=?
                WHERE txn_id=? AND status='pending' AND expires_at>?""",
                (profile_id,txn_id,now)).rowcount
            if updated != 1:
                return False
            db.execute("""UPDATE connections SET profile_id=?,expires_at=NULL
                WHERE client_id=? AND (profile_id IS NULL OR profile_id=?)""",
                (profile_id,txn["client_id"],profile_id))
            return True

    def resolve_pending_code(self, match_code, now=None):
        matches = [r["txn_id"] for r in self.pending(now) if r["match_code"] == match_code]
        if len(matches) != 1:
            raise ValueError(f"Match code ambiguous or missing ({len(matches)} matches): {matches}")
        return matches[0]

    def deny(self, txn_id, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            return db.execute("""UPDATE pending_txns SET status='denied'
                WHERE txn_id=? AND status='pending' AND expires_at>?""",
                (txn_id,now)).rowcount == 1

    def expire(self, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            return db.execute("""UPDATE pending_txns SET status='expired'
                WHERE status='pending' AND expires_at<=?""", (now,)).rowcount

    def revoke_connection(self, client_id, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("""UPDATE connections SET revoked_at=?
                WHERE client_id=? AND revoked_at IS NULL""",(now,client_id)).rowcount
            if changed:
                db.execute("UPDATE access_tokens SET revoked_at=? WHERE client_id=? AND revoked_at IS NULL",(now,client_id))
                db.execute("UPDATE refresh_tokens SET revoked_at=? WHERE client_id=? AND revoked_at IS NULL",(now,client_id))
                db.execute("UPDATE pending_txns SET status='denied' WHERE client_id=? AND status='pending'",(client_id,))
                db.execute("INSERT INTO revocations(target_type,target_id,created_at) VALUES('connection',?,?)",(client_id,now))
            return changed == 1

    def revoke_profile(self, profile_id, now=None):
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE profiles SET revoked_at=? WHERE profile_id=? AND revoked_at IS NULL",
                                 (now,profile_id)).rowcount
            if changed:
                ids = [r[0] for r in db.execute("SELECT client_id FROM connections WHERE profile_id=?",(profile_id,))]
                for cid in ids:
                    db.execute("UPDATE connections SET revoked_at=? WHERE client_id=?",(now,cid))
                    db.execute("UPDATE access_tokens SET revoked_at=? WHERE client_id=?",(now,cid))
                    db.execute("UPDATE refresh_tokens SET revoked_at=? WHERE client_id=?",(now,cid))
                    db.execute("UPDATE pending_txns SET status='denied' WHERE client_id=? AND status='pending'",(cid,))
                db.execute("INSERT INTO revocations(target_type,target_id,created_at) VALUES('profile',?,?)",(profile_id,now))
            return changed == 1

    def issue_auth_code(self, txn_id, now=None):
        """Issue one short-lived OAuth code after valid owner approval."""
        now = int(time.time()) if now is None else int(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""
                SELECT t.status, t.expires_at, t.resource,
                       t.approved_profile, c.profile_id,
                       c.revoked_at AS connection_revoked,
                       p.revoked_at AS profile_revoked
                FROM pending_txns t
                JOIN connections c ON c.client_id=t.client_id
                LEFT JOIN profiles p ON p.profile_id=t.approved_profile
                WHERE t.txn_id=?
            """, (txn_id,)).fetchone()
            if (row is None or row["status"] != "approved"
                    or row["expires_at"] <= now
                    or row["resource"] != CANONICAL_RESOURCE
                    or row["approved_profile"] is None
                    or row["approved_profile"] != row["profile_id"]
                    or row["connection_revoked"] is not None
                    or row["profile_revoked"] is not None):
                return None

            code = secrets.token_urlsafe(32)
            try:
                db.execute("""
                    INSERT INTO auth_codes(code_hash,txn_id,expires_at)
                    VALUES(?,?,?)
                """, (digest(code), txn_id, now + 540))
            except sqlite3.IntegrityError:
                return None
            return code

    def redeem_auth_code(self, code, client_id, redirect_uri,
                         code_verifier, resource, now=None):
        """Atomically validate and consume a single-use OAuth authorization code."""
        import base64
        import hmac

        now = int(time.time()) if now is None else int(now)
        if (not all(isinstance(v, str) and v for v in
                    (code, client_id, redirect_uri, code_verifier, resource))
                or resource != CANONICAL_RESOURCE
                or re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier) is None):
            return None

        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")

        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""
                SELECT a.used_at, a.expires_at AS code_expires,
                       t.txn_id, t.client_id, t.redirect_uri,
                       t.code_challenge, t.scopes, t.resource,
                       t.status, t.approved_profile,
                       c.profile_id, c.revoked_at AS connection_revoked,
                       p.revoked_at AS profile_revoked
                FROM auth_codes a
                JOIN pending_txns t ON t.txn_id=a.txn_id
                JOIN connections c ON c.client_id=t.client_id
                LEFT JOIN profiles p ON p.profile_id=t.approved_profile
                WHERE a.code_hash=?
            """, (digest(code),)).fetchone()

            if (row is None or row["used_at"] is not None
                    or row["code_expires"] <= now
                    or row["status"] != "approved"
                    or row["client_id"] != client_id
                    or row["redirect_uri"] != redirect_uri
                    or row["resource"] != resource
                    or row["approved_profile"] is None
                    or row["approved_profile"] != row["profile_id"]
                    or row["connection_revoked"] is not None
                    or row["profile_revoked"] is not None
                    or not hmac.compare_digest(row["code_challenge"], challenge)):
                return None

            updated = db.execute("""
                UPDATE auth_codes SET used_at=?
                WHERE code_hash=? AND used_at IS NULL AND expires_at>?
            """, (now, digest(code), now)).rowcount
            if updated != 1:
                return None

            consumed = db.execute("""
                UPDATE pending_txns SET status='consumed'
                WHERE txn_id=? AND status='approved'
            """, (row["txn_id"],)).rowcount
            if consumed != 1:
                raise sqlite3.IntegrityError(
                    "Authorization transaction consumption failed"
                )
            return {"client_id": client_id, "scopes": row["scopes"],
                    "resource": row["resource"], "txn_id": row["txn_id"]}

    def backup(self, destination):
        dest = Path(destination)
        if dest.exists():
            raise FileExistsError(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.connect() as source, sqlite3.connect(str(dest)) as target:
            source.backup(target)
        os.chmod(dest, 0o600)
