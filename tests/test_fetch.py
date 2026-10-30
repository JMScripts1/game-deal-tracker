import fetch_and_store
import queries
import watchlist
from conftest import make_deal
from db_setup import get_connection, setup_database
from fetch_and_store import deals_from_games, store_deals, sync_stores, update_lowest

GAMES = {
    "g1": {
        "info": {"title": "Hades", "thumb": "https://example.com/hades.jpg"},
        "cheapestPriceEver": {"price": "6.24", "date": 1758129350},
        "deals": [
            {"storeID": "1", "dealID": "steam-hades", "price": "24.99", "retailPrice": "24.99", "savings": "0.0"},
            {"storeID": "7", "dealID": "gog-hades", "price": "12.49", "retailPrice": "24.99", "savings": "50.02"},
        ],
    },
}


def test_deals_from_games_matches_deal_format():
    deals = deals_from_games(GAMES)
    assert len(deals) == 2
    assert deals[1] == {
        "dealID": "gog-hades", "gameID": "g1", "title": "Hades", "storeID": "7",
        "salePrice": "12.49", "normalPrice": "24.99", "savings": "50.02",
        "thumb": "https://example.com/hades.jpg", "steamAppID": None,
    }


def test_update_lowest_uses_cheapshark_record_only_when_lower(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 12.49, 24.99)], "2026-01-01T00:00:00")
    update_lowest(conn, GAMES)
    price, date = conn.execute("SELECT cheapest_ever, cheapest_ever_date FROM games").fetchone()
    assert price == 6.24
    assert date.startswith("2025-09")

    store_deals(conn, [make_deal("a", "g1", "Hades", 5, 24.99)], "2026-01-02T00:00:00")
    update_lowest(conn, GAMES)
    assert conn.execute("SELECT cheapest_ever FROM games").fetchone()[0] == 5


def test_update_lowest_prefers_earlier_date_for_same_price(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 6.24, 24.99)], "2026-01-01T00:00:00")
    update_lowest(conn, GAMES)
    price, date = conn.execute("SELECT cheapest_ever, cheapest_ever_date FROM games").fetchone()
    assert price == 6.24
    assert date.startswith("2025-09")


def test_fetch_includes_watched_games_outside_top_deals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "deals.db")
    conn = get_connection(db_path)
    setup_database(conn)
    sync_stores(conn, [{"storeID": "1", "storeName": "Steam"}, {"storeID": "7", "storeName": "GOG"}])
    watchlist.add(conn, "hades", 15)
    conn.close()

    top = [make_deal("c", "g2", "Celeste", 5, 20, "7")]
    monkeypatch.setattr(fetch_and_store, "get_deals", lambda **kwargs: top)
    monkeypatch.setattr(fetch_and_store, "search_games", lambda title, limit: [
        {"gameID": "g1", "external": "Hades"},
        {"gameID": "g9", "external": "Cool Shades"},  # fuzzy match that should be ignored
    ])
    requested = []

    def fake_get_games(ids):
        requested.append(set(ids))
        return {"g1": GAMES["g1"]}

    monkeypatch.setattr(fetch_and_store, "get_games", fake_get_games)

    games_added, deals_added = fetch_and_store.fetch_and_store(db_path=db_path)

    assert requested == [{"g1", "g2"}]
    assert (games_added, deals_added) == (2, 3)
    conn = get_connection(db_path)
    try:
        assert list(queries.watchlist_hits(conn)["store_name"]) == ["GOG"]
    finally:
        conn.close()
