import alerts
import notify
import watchlist
from conftest import make_deal
from fetch_and_store import store_deals


def snapshot(conn, day, hades_price, store_id="1"):
    store_deals(conn, [make_deal(f"hades-{store_id}", "g1", "Hades", hades_price, 25, store_id)],
                f"2026-01-{day:02d}T00:00:00")


def titles_and_prices(pending):
    return [(a["title"], a["sale_price"]) for a in pending]


def test_alert_only_once_until_price_drops(conn):
    watchlist.add(conn, "hades", 10)

    snapshot(conn, 1, 9)
    pending = alerts.pending_alerts(conn)
    assert titles_and_prices(pending) == [("Hades", 9)]
    alerts.mark_sent(conn, pending)

    snapshot(conn, 2, 9)
    assert alerts.pending_alerts(conn) == []

    snapshot(conn, 3, 7)
    assert titles_and_prices(alerts.pending_alerts(conn)) == [("Hades", 7)]


def test_alert_again_after_going_back_above_target(conn):
    watchlist.add(conn, "hades", 10)
    snapshot(conn, 1, 9)
    alerts.mark_sent(conn, alerts.pending_alerts(conn))

    snapshot(conn, 2, 20)
    assert alerts.pending_alerts(conn) == []

    snapshot(conn, 3, 9)
    assert titles_and_prices(alerts.pending_alerts(conn)) == [("Hades", 9)]


def test_alert_uses_cheapest_store(conn):
    watchlist.add(conn, "hades", 10)
    store_deals(conn, [make_deal("s", "g1", "Hades", 9, 25, "1"), make_deal("g", "g1", "Hades", 8, 25, "7")],
                "2026-01-01T00:00:00")
    [alert] = alerts.pending_alerts(conn)
    assert (alert["store_name"], alert["sale_price"], alert["deal_id"]) == ("GOG", 8, "g")


def test_removing_watch_clears_its_alerts(conn):
    watchlist.add(conn, "hades", 10)
    snapshot(conn, 1, 9)
    alerts.mark_sent(conn, alerts.pending_alerts(conn))
    watchlist.remove(conn, "hades")
    assert conn.execute("SELECT COUNT(*) FROM alerts_sent").fetchone()[0] == 0


def test_discord_batches_ten_embeds_per_message(conn, monkeypatch):
    watchlist.add(conn, "game", 10)
    store_deals(conn, [make_deal(f"d{i}", f"g{i}", f"Game {i}", 5, 20) for i in range(12)],
                "2026-01-01T00:00:00")
    pending = alerts.pending_alerts(conn)

    posts = []

    class Response:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notify.requests, "post", lambda url, json, timeout: posts.append(json) or Response())
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")

    assert notify.notify(pending)
    assert [len(p["embeds"]) for p in posts] == [10, 2]
    assert posts[0]["content"] == "12 watched games hit your target price"
    assert posts[0]["embeds"][0]["url"] == "https://www.cheapshark.com/redirect?dealID=d0"


def test_failed_discord_delivery_returns_false(conn, monkeypatch):
    def fail(*args, **kwargs):
        raise notify.requests.ConnectionError("offline")

    monkeypatch.setattr(notify.requests, "post", fail)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    watchlist.add(conn, "hades", 10)
    snapshot(conn, 1, 9)
    assert not notify.notify(alerts.pending_alerts(conn))
