# Fetches deal data from the CheapShark API and stores a snapshot in SQLite.

from datetime import datetime

from db_setup import get_connection, setup_database, title_matches
from fetch import get_deals, get_games, get_stores, search_games


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
            INSERT INTO games (game_id, title, cheapest_ever, cheapest_ever_date, thumb, steam_app_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (game_id) DO UPDATE SET
                title = excluded.title,
                thumb = COALESCE(excluded.thumb, games.thumb),
                steam_app_id = COALESCE(excluded.steam_app_id, games.steam_app_id),
                cheapest_ever_date = CASE
                    WHEN games.cheapest_ever IS NULL OR excluded.cheapest_ever < games.cheapest_ever
                    THEN excluded.cheapest_ever_date ELSE games.cheapest_ever_date END,
                cheapest_ever = MIN(COALESCE(games.cheapest_ever, excluded.cheapest_ever),
                                    excluded.cheapest_ever)
            """,
            (deal["gameID"], deal["title"], sale_price, fetched_at[:10], deal.get("thumb"),
             deal.get("steamAppID")),
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


def deals_from_games(games):
    """Flatten a /games lookup into the same deal format the /deals endpoint returns."""
    deals = []
    for game_id, game in games.items():
        for deal in game.get("deals", []):
            deals.append({
                "dealID": deal["dealID"],
                "gameID": game_id,
                "title": game["info"]["title"],
                "storeID": deal["storeID"],
                "salePrice": deal["price"],
                "normalPrice": deal["retailPrice"],
                "savings": deal["savings"],
                "thumb": game["info"].get("thumb"),
                "steamAppID": game["info"].get("steamAppID"),
            })
    return deals


def update_lowest(conn, games):
    """Apply CheapShark's historical low where it's lower than ours, or the same price but earlier."""
    for game_id, game in games.items():
        lowest = game.get("cheapestPriceEver") or {}
        if lowest.get("price") is None:
            continue
        date = datetime.fromtimestamp(lowest["date"]).date().isoformat() if lowest.get("date") else None
        price = float(lowest["price"])
        conn.execute(
            """
            UPDATE games SET cheapest_ever = ?, cheapest_ever_date = ?
            WHERE game_id = ? AND (
                cheapest_ever IS NULL
                OR ? < cheapest_ever - 0.001
                OR (ABS(? - cheapest_ever) <= 0.001 AND ? < COALESCE(cheapest_ever_date, '9999'))
            )
            """,
            (price, date, game_id, price, price, date),
        )
    conn.commit()


def watched_game_ids(conn, per_query=10):
    """Find CheapShark game ids for every watchlist entry."""
    ids = set()
    for (query,) in conn.execute("SELECT title_query FROM watchlist").fetchall():
        for game in search_games(query, limit=per_query):
            # CheapShark's search is fuzzy, so apply the same rule the watchlist report uses
            if title_matches(query, game["external"]):
                ids.add(game["gameID"])
    return ids


def fetch_and_store(pages=1, page_size=60, db_path=None):
    """Fetch deals plus every watched game and store them as one snapshot."""
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

        # Watched games are looked up directly, so they're tracked even when
        # they aren't among the top-rated deals
        watched = watched_game_ids(conn)
        games = get_games({d["gameID"] for d in deals} | watched)

        seen = {d["dealID"] for d in deals}
        watched_games = {gid: games[gid] for gid in watched if gid in games}
        deals.extend(d for d in deals_from_games(watched_games) if d["dealID"] not in seen)

        games_added, deals_added = store_deals(conn, deals)
        update_lowest(conn, games)
    finally:
        conn.close()

    print(f"Done: {games_added} new games, {deals_added} snapshots stored.")
    return games_added, deals_added


if __name__ == "__main__":
    fetch_and_store()
