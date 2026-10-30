import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_setup import get_connection, setup_database  # noqa: E402
from fetch_and_store import sync_stores  # noqa: E402


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
    conn = get_connection(":memory:")
    setup_database(conn)
    sync_stores(conn, [{"storeID": "1", "storeName": "Steam"}, {"storeID": "7", "storeName": "GOG"}])
    yield conn
    conn.close()
