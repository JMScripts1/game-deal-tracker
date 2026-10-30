# Database connection and schema setup

import os
import re
import sqlite3

DB_PATH = os.environ.get("DEALS_DB", "deals.db")


def title_matches(query, title):
    """Whole-word, case-insensitive match, so "Hades" matches "Hades II" but not "Shades"."""
    return re.search(rf"(?<!\w){re.escape(query)}(?!\w)", title, re.IGNORECASE) is not None


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    # Usable in SQL as title_matches(query, title)
    conn.create_function("title_matches", 2, lambda q, t: int(title_matches(q, t)), deterministic=True)
    return conn


def _add_column_if_missing(conn, table, column, definition):
    """Bring databases created by older versions up to the current schema."""
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def setup_database(conn):
    """Create all tables and indexes if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL
        );

        -- cheapest_ever is the historical low: CheapShark's record, or a
        -- lower price this tracker has observed since
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            cheapest_ever REAL,
            cheapest_ever_date TEXT,
            thumb TEXT,
            steam_app_id TEXT
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

        -- the price each watched game was last alerted at, so alerts don't repeat
        CREATE TABLE IF NOT EXISTS alerts_sent (
            watch_id INTEGER NOT NULL,
            game_id TEXT NOT NULL,
            price REAL NOT NULL,
            sent_at TEXT NOT NULL,
            PRIMARY KEY (watch_id, game_id),
            FOREIGN KEY (watch_id) REFERENCES watchlist (id) ON DELETE CASCADE,
            FOREIGN KEY (game_id) REFERENCES games (game_id)
        );

        CREATE INDEX IF NOT EXISTS idx_deals_fetched_at ON deals (fetched_at);
        CREATE INDEX IF NOT EXISTS idx_deals_game_id ON deals (game_id);
    """)
    _add_column_if_missing(conn, "games", "cheapest_ever_date", "TEXT")
    _add_column_if_missing(conn, "games", "thumb", "TEXT")
    _add_column_if_missing(conn, "games", "steam_app_id", "TEXT")
    conn.commit()


if __name__ == "__main__":
    conn = get_connection()
    setup_database(conn)
    conn.close()
    print(f"Database ready at {DB_PATH}.")
