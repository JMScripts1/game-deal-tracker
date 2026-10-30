# Database connection and schema setup

import os
import sqlite3

DB_PATH = os.environ.get("DEALS_DB", "deals.db")


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup_database(conn):
    """Create all tables and indexes if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL
        );

        -- cheapest_ever is the lowest sale price this tracker has observed
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            cheapest_ever REAL
        );

        -- one row per deal per fetch, so prices can be compared over time
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cheapshark_deal_id TEXT NOT NULL,
            game_id TEXT NOT NULL,
            store_id TEXT NOT NULL,
            sale_price REAL,
            normal_price REAL,
            discount_pct REAL,
            fetched_at TEXT NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games (game_id),
            FOREIGN KEY (store_id) REFERENCES stores (store_id),
            UNIQUE (cheapshark_deal_id, fetched_at)
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_query TEXT NOT NULL UNIQUE COLLATE NOCASE,
            target_price REAL NOT NULL,
            added_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_deals_fetched_at ON deals (fetched_at);
        CREATE INDEX IF NOT EXISTS idx_deals_game_id ON deals (game_id);
    """)
    conn.commit()


if __name__ == "__main__":
    conn = get_connection()
    setup_database(conn)
    conn.close()
    print(f"Database ready at {DB_PATH}.")
