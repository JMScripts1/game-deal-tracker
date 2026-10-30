import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queries
import watchlist
from db_setup import setup_database
from fetch_and_store import store_deals, sync_stores


def make_deal(deal_id, game_id, title, sale, normal, store_id="1"):
    return {
        "dealID": deal_id,
        "gameID": game_id,
        "title": title,
        "storeID": store_id,
        "salePrice": str(sale),
        "normalPrice": str(normal),
        "savings": str(round((1 - sale / normal) * 100, 4)),
    }


@pytest.fixture
def conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    setup_database(conn)
    sync_stores(conn, [{"storeID": "1", "storeName": "Steam"}, {"storeID": "7", "storeName": "GOG"}])
    yield conn
    conn.close()


def test_store_deals_counts_new_games_and_snapshots(conn):
    deals = [make_deal("a", "g1", "Hades", 10, 25), make_deal("b", "g2", "Celeste", 5, 20, "7")]
    assert store_deals(conn, deals, "2026-01-01T00:00:00") == (2, 2)
    assert store_deals(conn, deals, "2026-01-02T00:00:00") == (0, 2)


def test_same_snapshot_is_not_stored_twice(conn):
    deals = [make_deal("a", "g1", "Hades", 10, 25)]
    store_deals(conn, deals, "2026-01-01T00:00:00")
    assert store_deals(conn, deals, "2026-01-01T00:00:00") == (0, 0)


def test_cheapest_ever_only_goes_down(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 10, 25)], "2026-01-01T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 7.5, 25)], "2026-01-02T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 12, 25)], "2026-01-03T00:00:00")
    assert conn.execute("SELECT cheapest_ever FROM games").fetchone()[0] == 7.5


def test_unknown_store_gets_placeholder(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 10, 25, store_id="99")], "2026-01-01T00:00:00")
    assert conn.execute("SELECT store_name FROM stores WHERE store_id = '99'").fetchone()[0] == "Store 99"


def test_reports_use_latest_snapshot_only(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 5, 25)], "2026-01-01T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 20, 25)], "2026-01-02T00:00:00")

    top = queries.top_deals(conn)
    assert len(top) == 1
    assert top.iloc[0]["sale_price"] == 20

    assert queries.deals_by_store(conn).iloc[0]["deal_count"] == 1
    assert len(queries.price_history(conn, "hades")) == 2


def test_all_time_lows(conn):
    store_deals(conn, [make_deal("a", "g1", "Hades", 10, 25), make_deal("b", "g2", "Celeste", 8, 20)],
                "2026-01-01T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 9, 25), make_deal("b", "g2", "Celeste", 15, 20)],
                "2026-01-02T00:00:00")
    assert list(queries.all_time_lows(conn)["title"]) == ["Hades"]


def test_watchlist_hits(conn):
    watchlist.add(conn, "hades", 10)
    watchlist.add(conn, "celeste", 3)
    store_deals(conn, [make_deal("a", "g1", "Hades II", 9.99, 30), make_deal("b", "g2", "Celeste", 5, 20)],
                "2026-01-01T00:00:00")

    hits = queries.watchlist_hits(conn)
    assert list(hits["title"]) == ["Hades II"]


def test_watchlist_add_updates_and_remove(conn):
    watchlist.add(conn, "Hades", 10)
    watchlist.add(conn, "hades", 8)
    assert [(t, p) for t, p, _ in watchlist.entries(conn)] == [("Hades", 8)]
    assert watchlist.remove(conn, "HADES")
    assert not watchlist.remove(conn, "Hades")
