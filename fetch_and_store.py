# Fetches deal data from the CheapShark API and stores a snapshot in SQLite.

from datetime import datetime

from db_setup import get_connection, setup_database
from fetch import get_deals, get_stores


def sync_stores(conn, stores=None):
    """Insert or refresh store names. Returns the number of stores processed."""
    stores = stores if stores is not None else get_stores()
    conn.executemany(
        """
        INSERT INTO stores (store_id, store_name) VALUES (?, ?)
        ON CONFLICT (store_id) DO UPDATE SET store_name = excluded.store_name
        """,
        [(s["storeID"], s["storeName"]) for s in stores],
    )
    conn.commit()
    return len(stores)


def store_deals(conn, deals, fetched_at=None):
    """Store one snapshot of deals. Returns (new_games, snapshots_stored)."""
    fetched_at = fetched_at or datetime.now().isoformat(timespec="seconds")
    games_before = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    deals_added = 0

    for deal in deals:
        sale_price = float(deal["salePrice"])

        # A store we haven't synced yet shouldn't break the foreign key
        conn.execute(
            "INSERT OR IGNORE INTO stores (store_id, store_name) VALUES (?, ?)",
            (deal["storeID"], f"Store {deal['storeID']}"),
        )

        # Insert the game, or lower its cheapest_ever if this price beats it
        conn.execute(
            """
            INSERT INTO games (game_id, title, cheapest_ever) VALUES (?, ?, ?)
            ON CONFLICT (game_id) DO UPDATE SET
                title = excluded.title,
                cheapest_ever = MIN(COALESCE(games.cheapest_ever, excluded.cheapest_ever),
                                    excluded.cheapest_ever)
            """,
            (deal["gameID"], deal["title"], sale_price),
        )

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO deals
            (cheapshark_deal_id, game_id, store_id, sale_price,
             normal_price, discount_pct, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal["dealID"],
                deal["gameID"],
                deal["storeID"],
                sale_price,
                float(deal["normalPrice"]),
                float(deal["savings"]),
                fetched_at,
            ),
        )
        deals_added += cursor.rowcount

    conn.commit()
    games_after = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    return games_after - games_before, deals_added


def fetch_and_store(pages=1, page_size=60, db_path=None):
    """Fetch `pages` pages of deals from CheapShark and store them as one snapshot."""
    print(f"Fetching at {datetime.now().strftime('%H:%M:%S')}...")
    conn = get_connection(db_path)
    try:
        setup_database(conn)

        # Pull real store names the first time round
        if conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0] == 0:
            sync_stores(conn)

        deals = []
        for page in range(pages):
            batch = get_deals(page_size=page_size, page_number=page)
            deals.extend(batch)
            if len(batch) < page_size:
                break

        games_added, deals_added = store_deals(conn, deals)
    finally:
        conn.close()

    print(f"Done: {games_added} new games, {deals_added} snapshots stored.")
    return games_added, deals_added


if __name__ == "__main__":
    fetch_and_store()
