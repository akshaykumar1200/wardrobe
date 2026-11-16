import sqlite3
import hashlib
import secrets
from pathlib import Path

DB_PATH = Path("wardrobe.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # High-concurrency WAL mode & foreign key integrity
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def init_db():
    conn = get_conn()
    
    # 1. Base tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            token         TEXT UNIQUE,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER DEFAULT 1,
            category      TEXT NOT NULL,
            image_path    TEXT NOT NULL,
            color         TEXT,
            color_name    TEXT,
            colors_json   TEXT,
            pattern       TEXT DEFAULT 'solid',
            pattern_scale TEXT DEFAULT 'none',
            area          INTEGER DEFAULT 0,
            confidence    REAL,
            label         TEXT,
            wear_count    INTEGER DEFAULT 0,
            last_worn     TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS outfits (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER DEFAULT 1,
            item_ids      TEXT NOT NULL,
            score         REAL,
            verdict       TEXT,
            palette_json  TEXT,
            stylist_notes TEXT,
            worn_on       TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    # 2. Safe migrations for existing items table
    item_cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    new_item_cols = [
        ("user_id", "INTEGER DEFAULT 1"),
        ("color_name", "TEXT"),
        ("colors_json", "TEXT"),
        ("pattern", "TEXT DEFAULT 'solid'"),
        ("pattern_scale", "TEXT DEFAULT 'none'"),
        ("area", "INTEGER DEFAULT 0"),
        ("confidence", "REAL"),
    ]
    for col_name, col_type in new_item_cols:
        if col_name not in item_cols:
            try:
                conn.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    outfit_cols = [r[1] for r in conn.execute("PRAGMA table_info(outfits)").fetchall()]
    new_outfit_cols = [
        ("user_id", "INTEGER DEFAULT 1"),
        ("score", "REAL"),
        ("verdict", "TEXT"),
        ("palette_json", "TEXT"),
        ("stylist_notes", "TEXT"),
    ]
    for col_name, col_type in new_outfit_cols:
        if col_name not in outfit_cols:
            try:
                conn.execute(f"ALTER TABLE outfits ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    # 3. Safe indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outfits_user ON outfits(user_id)")

    # 4. Ensure demo user exists
    demo_user = conn.execute("SELECT * FROM users WHERE username = 'demo'").fetchone()
    if not demo_user:
        salt = secrets.token_hex(16)
        pw_hash = _hash_password("demo123", salt)
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, token) VALUES (?, ?, ?, ?)",
            ("demo", pw_hash, salt, token)
        )

    conn.commit()
    conn.close()


# ---------- User Management & Auth Helpers ----------

def create_user(username: str, password: str) -> dict:
    conn = get_conn()
    username = username.strip().lower()
    if not username:
        conn.close()
        raise ValueError("Username cannot be empty")
    if not password:
        conn.close()
        raise ValueError("Password cannot be empty")

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Username '{username}' already exists. Please sign in.")

    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    token = secrets.token_hex(32)

    cur = conn.execute(
        "INSERT INTO users (username, password_hash, salt, token) VALUES (?, ?, ?, ?)",
        (username, pw_hash, salt, token)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "username": username, "token": token}


def authenticate_user(username: str, password: str) -> tuple[dict | None, str]:
    """
    Returns (user_dict, status_code_string)
    status_code_string can be: 'ok', 'user_not_found', 'wrong_password'
    """
    conn = get_conn()
    username = username.strip().lower()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        return None, "user_not_found"

    pw_hash = _hash_password(password, user["salt"])
    if pw_hash != user["password_hash"]:
        conn.close()
        return None, "wrong_password"

    # Refresh / return token
    token = user["token"]
    if not token:
        token = secrets.token_hex(32)
        conn.execute("UPDATE users SET token = ? WHERE id = ?", (token, user["id"]))
        conn.commit()

    conn.close()
    return {"id": user["id"], "username": user["username"], "token": token}, "ok"


def get_user_by_token(token: str) -> dict | None:
    if not token:
        return None
    conn = get_conn()
    user = conn.execute("SELECT id, username, created_at FROM users WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(user) if user else None


def logout_user(token: str):
    if not token:
        return
    conn = get_conn()
    conn.execute("UPDATE users SET token = NULL WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def get_all_registered_image_paths() -> set[str]:
    """Returns a set of all relative file paths currently stored in items table."""
    conn = get_conn()
    rows = conn.execute("SELECT image_path FROM items").fetchall()
    conn.close()
    return {r["image_path"].lstrip("/") for r in rows if r["image_path"]}
