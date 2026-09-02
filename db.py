"""
db.py — PostgreSQL & SQL data-access layer for the LADLI backend.

Supports PostgreSQL via psycopg2 (with connection pooling, dictionary cursors,
and automatic schema initialization) with automatic environment detection
from DATABASE_URL or individual PG* settings.
"""

import os
import re
import secrets
import string
import datetime
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "ladli.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
PGHOST = os.environ.get("PGHOST")
PGPORT = os.environ.get("PGPORT", "5432")
PGDATABASE = os.environ.get("PGDATABASE")
PGUSER = os.environ.get("PGUSER")
PGPASSWORD = os.environ.get("PGPASSWORD")
PGSSLMODE = os.environ.get("PGSSLMODE", "prefer")

_pg_pool = None


def is_postgres_configured():
    """Returns True if PostgreSQL connection parameters are configured."""
    return bool(DATABASE_URL or (PGHOST and PGDATABASE and PGUSER))


def get_pg_connection_params():
    """Parses DATABASE_URL or individual PG* env vars into a connection dict."""
    if DATABASE_URL:
        # Handle postgres:// vs postgresql:// protocol
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql://" + url[11:]
        parsed = urlparse(url)
        return {
            "dbname": parsed.path.lstrip("/"),
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "sslmode": PGSSLMODE if parsed.hostname not in ("localhost", "127.0.0.1") else "prefer",
        }
    return {
        "dbname": PGDATABASE,
        "user": PGUSER,
        "password": PGPASSWORD,
        "host": PGHOST,
        "port": int(PGPORT) if PGPORT else 5432,
        "sslmode": PGSSLMODE,
    }


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None and PSYCOPG2_AVAILABLE and is_postgres_configured():
        params = get_pg_connection_params()
        _pg_pool = pool.SimpleConnectionPool(1, 20, **params)
    return _pg_pool


# ---------------------------------------------------------------------------
# Unified Database Cursor & Connection Wrapper
# ---------------------------------------------------------------------------
class PostgresCursorWrapper:
    """Wraps psycopg2 RealDictCursor to provide uniform row access and rowcount."""

    def __init__(self, cursor, conn):
        self._cursor = cursor
        self._conn = conn

    def execute(self, sql, params=None):
        # Translate '?' placeholders to '%s' if necessary
        formatted_sql = sql
        if "?" in formatted_sql and "%s" not in formatted_sql:
            formatted_sql = formatted_sql.replace("?", "%s")
        
        # Translate SQLite-specific keywords to standard PostgreSQL
        formatted_sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)", r"INSERT INTO \1", formatted_sql, flags=re.IGNORECASE)
        
        if params is not None:
            if isinstance(params, (list, tuple)):
                self._cursor.execute(formatted_sql, params)
            else:
                self._cursor.execute(formatted_sql, (params,))
        else:
            self._cursor.execute(formatted_sql)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class PostgresConnectionWrapper:
    """Wraps a psycopg2 connection to provide a clean SQLite-like interface."""

    def __init__(self, raw_conn, from_pool=False):
        self._conn = raw_conn
        self._from_pool = from_pool
        self._closed = False

    def execute(self, sql, params=None):
        cursor = self._conn.cursor(cursor_factory=RealDictCursor)
        wrapper = PostgresCursorWrapper(cursor, self)
        wrapper.execute(sql, params)
        return wrapper

    def executescript(self, script):
        with self._conn.cursor() as cur:
            cur.execute(script)
        self._conn.commit()

    def commit(self):
        if not self._closed:
            self._conn.commit()

    def rollback(self):
        if not self._closed:
            self._conn.rollback()

    def close(self):
        if not self._closed:
            self._closed = True
            if self._from_pool and _pg_pool is not None:
                _pg_pool.putconn(self._conn)
            else:
                self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


class SQLiteConnectionWrapper:
    """Wraps sqlite3 connection with dictionary row access and uniform interface."""

    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        # Convert %s back to ? if PostgreSQL syntax was passed
        formatted_sql = sql
        if "%s" in formatted_sql:
            formatted_sql = formatted_sql.replace("%s", "?")
        if params is not None:
            return self._conn.execute(formatted_sql, params)
        return self._conn.execute(formatted_sql)

    def executescript(self, script):
        return self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_db():
    """
    Returns an active database connection wrapper.
    Connects to PostgreSQL if configured, otherwise falls back to SQLite.
    """
    if PSYCOPG2_AVAILABLE and is_postgres_configured():
        try:
            pool_instance = _get_pg_pool()
            if pool_instance:
                conn = pool_instance.getconn()
                return PostgresConnectionWrapper(conn, from_pool=True)
            params = get_pg_connection_params()
            conn = psycopg2.connect(**params)
            return PostgresConnectionWrapper(conn, from_pool=False)
        except Exception as e:
            # Fallback to direct connect or raise
            raise RuntimeError(f"Could not connect to PostgreSQL database: {e}")

    if SQLITE_AVAILABLE:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return SQLiteConnectionWrapper(conn)

    raise RuntimeError("No supported database driver (psycopg2 or sqlite3) is available.")


# ---------------------------------------------------------------------------
# Database Schema Definitions
# ---------------------------------------------------------------------------
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_users (
    id                   SERIAL PRIMARY KEY,
    username             VARCHAR(150) UNIQUE NOT NULL,
    password_hash        TEXT NOT NULL,
    created_at           VARCHAR(50) NOT NULL,
    must_change_password SMALLINT NOT NULL DEFAULT 0,
    email                VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS password_history (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(150) NOT NULL,
    password_hash TEXT NOT NULL,
    changed_at    VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id           SERIAL PRIMARY KEY,
    username     VARCHAR(150) NOT NULL,
    ip_address   VARCHAR(100) NOT NULL,
    attempted_at VARCHAR(50) NOT NULL,
    success      SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inquiries (
    id                       SERIAL PRIMARY KEY,
    kind                     VARCHAR(50) NOT NULL,
    name                     TEXT,
    company                  TEXT,
    phone                    TEXT,
    email                    TEXT,
    message                  TEXT,
    extra_json               TEXT,
    status                   VARCHAR(50) NOT NULL DEFAULT 'new',
    created_at               VARCHAR(50) NOT NULL,
    attachment_filename      TEXT,
    attachment_original_name TEXT,
    attachment_size_bytes    BIGINT
);

CREATE TABLE IF NOT EXISTS visitor_stats (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    manual_count INTEGER NOT NULL DEFAULT 0,
    mode         VARCHAR(50) NOT NULL DEFAULT 'auto',
    updated_at   VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS unique_visitors (
    visitor_token VARCHAR(128) PRIMARY KEY,
    first_seen    VARCHAR(50) NOT NULL,
    last_seen     VARCHAR(50) NOT NULL
);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT UNIQUE NOT NULL,
    password_hash        TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    email                TEXT
);

CREATE TABLE IF NOT EXISTS password_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    changed_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL,
    ip_address   TEXT NOT NULL,
    attempted_at TEXT NOT NULL,
    success      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inquiries (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind                     TEXT NOT NULL,
    name                     TEXT,
    company                  TEXT,
    phone                    TEXT,
    email                    TEXT,
    message                  TEXT,
    extra_json               TEXT,
    status                   TEXT NOT NULL DEFAULT 'new',
    created_at               TEXT NOT NULL,
    attachment_filename      TEXT,
    attachment_original_name TEXT,
    attachment_size_bytes    INTEGER
);

CREATE TABLE IF NOT EXISTS visitor_stats (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    manual_count INTEGER NOT NULL DEFAULT 0,
    mode         TEXT NOT NULL DEFAULT 'auto',
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS unique_visitors (
    visitor_token TEXT PRIMARY KEY,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
"""


def _migrate(conn):
    """Ensures default visitor_stats record exists and runs migrations."""
    now = datetime.datetime.utcnow().isoformat()
    if is_postgres_configured():
        conn.execute(
            "INSERT INTO visitor_stats (id, manual_count, mode, updated_at) "
            "VALUES (1, 0, 'auto', %s) ON CONFLICT (id) DO NOTHING",
            (now,),
        )
        conn.execute("UPDATE visitor_stats SET mode = 'auto' WHERE mode = 'real'")
    else:
        conn.execute(
            "INSERT OR IGNORE INTO visitor_stats (id, manual_count, mode, updated_at) "
            "VALUES (1, 0, 'auto', ?)",
            (now,),
        )
        conn.execute("UPDATE visitor_stats SET mode = 'auto' WHERE mode = 'real'")
    conn.commit()


def generate_strong_password(length=16):
    """Generates a cryptographically strong random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*-_=+" for c in pwd)
        ):
            return pwd


def init_db(default_username="admin", default_password=None, default_email=None):
    """Initializes the database schema and creates initial admin if missing."""
    conn = get_db()
    if is_postgres_configured():
        conn.executescript(POSTGRES_SCHEMA)
    else:
        conn.executescript(SQLITE_SCHEMA)

    _migrate(conn)

    existing_row = conn.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()
    existing = existing_row["c"] if existing_row else 0
    if existing == 0:
        generated = default_password is None
        password = default_password or generate_strong_password()
        now = datetime.datetime.utcnow().isoformat()
        password_hash = generate_password_hash(password)

        conn.execute(
            "INSERT INTO admin_users (username, password_hash, created_at, must_change_password, email) "
            "VALUES (%s, %s, %s, %s, %s)",
            (default_username, password_hash, now, 1 if generated else 0, default_email),
        )
        conn.execute(
            "INSERT INTO password_history (username, password_hash, changed_at) VALUES (%s, %s, %s)",
            (default_username, password_hash, now),
        )
        conn.commit()
        db_type = "PostgreSQL" if is_postgres_configured() else "SQLite"
        print("=" * 64)
        print(f" First run ({db_type}): an admin account was created.")
        print(f"   Username: {default_username}")
        if generated:
            print(f"   Password: {password}")
            print(" This password was randomly generated and is shown ONLY")
            print(" here, once. Save it now. You will be required to change")
            print(" it the moment you log in at /admin.")
        else:
            print(" Password: (the value of ADMIN_PASSWORD in your .env)")
        print("=" * 64)
    conn.commit()
    conn.close()


def _humanize_delta(changed_at_iso):
    """'3 hours ago' / '2 days ago' style label for a past ISO timestamp."""
    try:
        changed_at = datetime.datetime.fromisoformat(changed_at_iso)
    except Exception:
        return "recently"
    delta = datetime.datetime.utcnow() - changed_at
    seconds = max(delta.total_seconds(), 0)
    if seconds < 3600:
        minutes = max(int(seconds // 60), 1)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def record_password_history(username, password_hash):
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO password_history (username, password_hash, changed_at) VALUES (%s, %s, %s)",
        (username, password_hash, now),
    )
    # Keep only the last 5 hashes per account
    conn.execute(
        "DELETE FROM password_history WHERE username = %s AND id NOT IN "
        "(SELECT id FROM password_history WHERE username = %s ORDER BY id DESC LIMIT 5)",
        (username, username),
    )
    conn.commit()
    conn.close()


def find_password_in_history(username, plaintext_password, current_hash):
    from werkzeug.security import check_password_hash

    conn = get_db()
    rows = conn.execute(
        "SELECT password_hash, changed_at FROM password_history "
        "WHERE username = %s ORDER BY id DESC",
        (username,),
    ).fetchall()
    conn.close()
    for row in rows:
        if row["password_hash"] == current_hash:
            continue
        if check_password_hash(row["password_hash"], plaintext_password):
            return _humanize_delta(row["changed_at"])
    return None


# ---------------------------------------------------------------------------
# Login lockout (brute-force protection)
# ---------------------------------------------------------------------------
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15


def record_login_attempt(username, ip_address, success):
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO login_attempts (username, ip_address, attempted_at, success) VALUES (%s, %s, %s, %s)",
        (username.lower(), ip_address, now, 1 if success else 0),
    )
    cutoff = (
        datetime.datetime.utcnow() - datetime.timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    ).isoformat()
    conn.execute("DELETE FROM login_attempts WHERE attempted_at < %s", (cutoff,))
    conn.commit()
    conn.close()


def is_locked_out(username, ip_address):
    cutoff = (
        datetime.datetime.utcnow() - datetime.timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    ).isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE username = %s AND ip_address = %s AND success = 0 AND attempted_at >= %s",
        (username.lower(), ip_address, cutoff),
    ).fetchone()
    conn.close()
    return (row["c"] if row else 0) >= LOCKOUT_MAX_ATTEMPTS


def clear_login_attempts(username, ip_address):
    conn = get_db()
    conn.execute(
        "DELETE FROM login_attempts WHERE username = %s AND ip_address = %s",
        (username.lower(), ip_address),
    )
    conn.commit()
    conn.close()


def clear_all_login_attempts_for_user(username):
    conn = get_db()
    conn.execute(
        "DELETE FROM login_attempts WHERE username = %s",
        (username.lower(),),
    )
    conn.commit()
    conn.close()


def set_must_change_password(username, value=True):
    conn = get_db()
    conn.execute(
        "UPDATE admin_users SET must_change_password = %s WHERE username = %s",
        (1 if value else 0, username),
    )
    conn.commit()
    conn.close()


def find_admin_by_username_or_email(identifier):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM admin_users WHERE lower(username) = lower(%s) OR lower(email) = lower(%s)",
        (identifier, identifier),
    ).fetchone()
    conn.close()
    return row


def set_password(username, new_password_plain):
    new_hash = generate_password_hash(new_password_plain)
    conn = get_db()
    conn.execute(
        "UPDATE admin_users SET password_hash = %s, must_change_password = 0 WHERE username = %s",
        (new_hash, username),
    )
    conn.commit()
    conn.close()
    record_password_history(username, new_hash)
    clear_all_login_attempts_for_user(username)
    return new_hash


# ---------------------------------------------------------------------------
# Visitor Management
# ---------------------------------------------------------------------------
def get_visitor_stats():
    conn = get_db()
    row = conn.execute("SELECT * FROM visitor_stats WHERE id = 1").fetchone()
    conn.close()
    return row


def set_visitor_mode(mode):
    if mode not in ("auto", "manual"):
        raise ValueError("mode must be 'auto' or 'manual'")
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE visitor_stats SET mode = %s, updated_at = %s WHERE id = 1",
        (mode, now),
    )
    conn.commit()
    conn.close()


def set_manual_count(count):
    count = max(0, int(count))
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE visitor_stats SET manual_count = %s, updated_at = %s WHERE id = 1",
        (count, now),
    )
    conn.commit()
    conn.close()


def record_unique_visitor(visitor_token):
    now = datetime.datetime.utcnow().isoformat()
    conn = get_db()
    
    if is_postgres_configured():
        cur = conn.execute(
            "INSERT INTO unique_visitors (visitor_token, first_seen, last_seen) "
            "VALUES (%s, %s, %s) ON CONFLICT (visitor_token) DO NOTHING",
            (visitor_token, now, now),
        )
    else:
        cur = conn.execute(
            "INSERT OR IGNORE INTO unique_visitors (visitor_token, first_seen, last_seen) "
            "VALUES (?, ?, ?)",
            (visitor_token, now, now),
        )

    is_new = cur.rowcount > 0
    if not is_new:
        conn.execute(
            "UPDATE unique_visitors SET last_seen = %s WHERE visitor_token = %s",
            (now, visitor_token),
        )
    conn.commit()
    count_row = conn.execute("SELECT COUNT(*) AS c FROM unique_visitors").fetchone()
    total = count_row["c"] if count_row else 0
    conn.close()
    return is_new, total


def get_unique_visitor_count():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS c FROM unique_visitors").fetchone()
    conn.close()
    return row["c"] if row else 0


def get_display_visitor_count():
    row = get_visitor_stats()
    if row and row["mode"] == "manual":
        return row["manual_count"], "manual"
    return get_unique_visitor_count(), "auto"