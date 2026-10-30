from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db_setup
import watchlist
from conftest import make_deal
from fetch_and_store import store_deals, sync_stores

DASHBOARD = str(Path(__file__).resolve().parent.parent / "dashboard.py")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "deals.db")
    monkeypatch.setattr(db_setup, "DB_PATH", path)
    return path


def test_dashboard_renders_empty_database(db_path):
    app = AppTest.from_file(DASHBOARD).run(timeout=30)
    assert not app.exception
    assert "No deals yet" in app.info[0].value


def test_dashboard_renders_with_data(db_path):
    conn = db_setup.get_connection(db_path)
    db_setup.setup_database(conn)
    sync_stores(conn, [{"storeID": "1", "storeName": "Steam"}, {"storeID": "7", "storeName": "GOG"}])
    watchlist.add(conn, "hades", 15)
    store_deals(conn, [make_deal("a", "g1", "Hades", 12, 25), make_deal("b", "g2", "Celeste", 5, 20, "7")],
                "2026-01-01T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 10, 25), make_deal("b", "g2", "Celeste", 5, 20, "7")],
                "2026-01-02T00:00:00")
    conn.close()

    app = AppTest.from_file(DASHBOARD).run(timeout=30)
    assert not app.exception
    assert [m.value for m in app.metric] == ["2", "68%", "2", "1"]

    app.text_input(key="history_search").input("hades").run(timeout=30)
    assert not app.exception
    assert app.selectbox[0].value == "Hades"
