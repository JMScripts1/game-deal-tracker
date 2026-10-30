from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db_setup
import queries
import watchlist
from conftest import make_deal
from fetch_and_store import store_deals, sync_stores

DASHBOARD = str(Path(__file__).resolve().parent.parent / "dashboard.py")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "deals.db")
    monkeypatch.setattr(db_setup, "DB_PATH", path)
    return path


def page_html(app):
    return "".join(m.value for m in app.markdown)


def seed(db_path):
    conn = db_setup.get_connection(db_path)
    db_setup.setup_database(conn)
    sync_stores(conn, [{"storeID": "1", "storeName": "Steam"}, {"storeID": "7", "storeName": "GOG"}])
    watchlist.add(conn, "hades", 15)
    watchlist.add(conn, "celeste", 2)
    store_deals(conn, [make_deal("a", "g1", "Hades", 12, 25), make_deal("b", "g2", "Celeste", 5, 20, "7")],
                "2026-01-01T00:00:00")
    store_deals(conn, [make_deal("a", "g1", "Hades", 10, 25), make_deal("b", "g2", "Celeste", 5, 20, "7")],
                "2026-01-02T00:00:00")
    return conn


def test_dashboard_renders_empty_database(db_path):
    app = AppTest.from_file(DASHBOARD).run(timeout=30)
    assert not app.exception
    assert "No deals yet" in page_html(app)


def test_dashboard_renders_with_data(db_path):
    seed(db_path).close()

    app = AppTest.from_file(DASHBOARD).run(timeout=30)
    assert not app.exception
    page = page_html(app)
    assert "Biggest drop right now" in page
    assert "On your watchlist" in page
    assert "&#36;5.00 under your target" in page  # Hades at $10 against a $15 target
    assert page.count('class="card"') >= 3  # one watchlist card plus a card per game

    app.segmented_control(key="deal_view").set_value("Table").run(timeout=30)
    assert not app.exception
    assert len(app.dataframe) == 1

    app.text_input(key="history_search").input("hades").run(timeout=30)
    assert not app.exception
    assert app.selectbox[-1].value == "Hades"  # the game picker comes after the deals sort box


def test_watchlist_status_reports_best_match_or_nothing(db_path):
    conn = seed(db_path)
    watchlist.add(conn, "portal", 5)
    status = queries.watchlist_status(conn).set_index("title_query")
    conn.close()

    assert status.loc["hades", "sale_price"] == 10
    assert status.loc["celeste", "sale_price"] == 5  # above its $2 target, still reported
    assert status["sale_price"].isna()["portal"]
