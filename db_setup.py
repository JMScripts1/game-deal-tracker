import sqlite3

def setup_database():
    conn = sqlite3.connect("deals.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            cheapest_ever REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            store_id TEXT NOT NULL,
            sale_price REAL,
            normal_price REAL,
            discount_pct REAL,
            fetched_at TEXT,
            FOREIGN KEY (game_id) REFERENCES games (game_id),
            FOREIGN KEY (store_id) REFERENCES stores (store_id)
        )
    """)

    conn.commit()
    conn.close()
    print("Database created.")

if __name__ == "__main__":
    setup_database()