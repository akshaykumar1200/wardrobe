"""
db.py for f6 AI Fashion Wardrobe
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("wardrobe.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,          -- topwear, bottomwear, shoes, accessories, other
            image_path TEXT NOT NULL,
            color_hex TEXT NOT NULL,
            color_name TEXT,
            colors_json TEXT,                -- full palette list JSON
            pattern TEXT DEFAULT 'solid',    -- solid, striped, plaid, etc.
            pattern_scale TEXT DEFAULT 'none',-- none, fine, medium, bold
            area INTEGER DEFAULT 0,
            confidence REAL,
            wear_count INTEGER DEFAULT 0,
            last_worn TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS outfits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            item_ids TEXT NOT NULL,          -- JSON list of item IDs
            score REAL,
            verdict TEXT,
            palette_json TEXT,
            stylist_notes TEXT,
            worn_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY,
            sha256 TEXT UNIQUE,
            file_name TEXT,
            is_worn BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
