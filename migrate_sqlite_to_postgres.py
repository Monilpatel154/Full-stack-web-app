"""
migrate_sqlite_to_postgres.py — Migrate all data from SQLite (ladli.db) to PostgreSQL.

Usage:
    python migrate_sqlite_to_postgres.py

Requirements:
    - Set DATABASE_URL or (PGHOST, PGDATABASE, PGUSER, PGPASSWORD) in your .env
    - Existing data/ladli.db file
"""

import os
import sqlite3
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "data", "ladli.db")


def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v


def migrate():
    load_env()

    if not os.path.isfile(SQLITE_DB_PATH):
        print(f"[!] SQLite database not found at: {SQLITE_DB_PATH}")
        return

    if not db.is_postgres_configured():
        print("[!] PostgreSQL is not configured in .env or environment.")
        print("    Please set DATABASE_URL (or PGHOST, PGDATABASE, PGUSER, PGPASSWORD) first.")
        return

    print("=" * 64)
    print(" LADLI — SQLite to PostgreSQL Data Migration Tool")
    print("=" * 64)

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    # 2. Connect to PostgreSQL
    pg_params = db.get_pg_connection_params()
    print(f"Connecting to PostgreSQL database '{pg_params.get('dbname')}' at {pg_params.get('host') or 'localhost'}...")
    pg_conn = psycopg2.connect(**pg_params)

    # 3. Ensure PostgreSQL tables exist
    with pg_conn.cursor() as cur:
        cur.execute(db.POSTGRES_SCHEMA)
    pg_conn.commit()

    # 4. Migrate admin_users
    sqlite_admins = sqlite_conn.execute("SELECT * FROM admin_users").fetchall()
    migrated_admins = 0
    with pg_conn.cursor() as cur:
        for r in sqlite_admins:
            cur.execute(
                """
                INSERT INTO admin_users (id, username, password_hash, created_at, must_change_password, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                """,
                (
                    r["id"],
                    r["username"],
                    r["password_hash"],
                    r["created_at"],
                    r["must_change_password"],
                    r["email"] if "email" in r.keys() else None,
                ),
            )
            if cur.rowcount > 0:
                migrated_admins += 1
    pg_conn.commit()
    print(f"  [+] admin_users: {migrated_admins} / {len(sqlite_admins)} migrated")

    # 5. Migrate password_history
    sqlite_pwd = sqlite_conn.execute("SELECT * FROM password_history").fetchall()
    migrated_pwd = 0
    with pg_conn.cursor() as cur:
        for r in sqlite_pwd:
            cur.execute(
                """
                INSERT INTO password_history (id, username, password_hash, changed_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (r["id"], r["username"], r["password_hash"], r["changed_at"]),
            )
            if cur.rowcount > 0:
                migrated_pwd += 1
    pg_conn.commit()
    print(f"  [+] password_history: {migrated_pwd} / {len(sqlite_pwd)} migrated")

    # 6. Migrate inquiries
    sqlite_inquiries = sqlite_conn.execute("SELECT * FROM inquiries").fetchall()
    migrated_inquiries = 0
    with pg_conn.cursor() as cur:
        for r in sqlite_inquiries:
            cur.execute(
                """
                INSERT INTO inquiries (
                    id, kind, name, company, phone, email, message, extra_json,
                    status, created_at, attachment_filename, attachment_original_name, attachment_size_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    r["id"],
                    r["kind"],
                    r["name"],
                    r["company"],
                    r["phone"],
                    r["email"],
                    r["message"],
                    r["extra_json"],
                    r["status"],
                    r["created_at"],
                    r["attachment_filename"],
                    r["attachment_original_name"],
                    r["attachment_size_bytes"],
                ),
            )
            if cur.rowcount > 0:
                migrated_inquiries += 1
    pg_conn.commit()
    print(f"  [+] inquiries: {migrated_inquiries} / {len(sqlite_inquiries)} migrated")

    # 7. Migrate visitor_stats
    sqlite_stats = sqlite_conn.execute("SELECT * FROM visitor_stats WHERE id = 1").fetchone()
    if sqlite_stats:
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO visitor_stats (id, manual_count, mode, updated_at)
                VALUES (1, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    manual_count = EXCLUDED.manual_count,
                    mode = EXCLUDED.mode,
                    updated_at = EXCLUDED.updated_at
                """,
                (sqlite_stats["manual_count"], sqlite_stats["mode"], sqlite_stats["updated_at"]),
            )
        pg_conn.commit()
        print("  [+] visitor_stats: synchronized")

    # 8. Migrate unique_visitors
    sqlite_visitors = sqlite_conn.execute("SELECT * FROM unique_visitors").fetchall()
    migrated_visitors = 0
    with pg_conn.cursor() as cur:
        for r in sqlite_visitors:
            cur.execute(
                """
                INSERT INTO unique_visitors (visitor_token, first_seen, last_seen)
                VALUES (%s, %s, %s)
                ON CONFLICT (visitor_token) DO NOTHING
                """,
                (r["visitor_token"], r["first_seen"], r["last_seen"]),
            )
            if cur.rowcount > 0:
                migrated_visitors += 1
    pg_conn.commit()
    print(f"  [+] unique_visitors: {migrated_visitors} / {len(sqlite_visitors)} migrated")

    # 9. Sync PostgreSQL serial sequences
    with pg_conn.cursor() as cur:
        for table, seq in [
            ("admin_users", "admin_users_id_seq"),
            ("password_history", "password_history_id_seq"),
            ("inquiries", "inquiries_id_seq"),
        ]:
            cur.execute(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1))")
    pg_conn.commit()

    sqlite_conn.close()
    pg_conn.close()

    print("=" * 64)
    print(" Migration completed successfully with zero errors!")
    print("=" * 64)


if __name__ == "__main__":
    migrate()
