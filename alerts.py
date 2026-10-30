# Decides which watchlist hits are new, so the same deal isn't alerted on every fetch.
#
# A game alerts once when it reaches its target price, and again only if the
# price drops further. If it goes back above target, it can alert again the
# next time it drops below.

from datetime import datetime

from queries import AT_LOW, LATEST


def current_hits(conn):
    """The cheapest qualifying deal for each (watchlist entry, game) in the latest snapshot."""
    # SQLite returns the other columns from the row holding MIN(sale_price)
    rows = conn.execute(f"""
        SELECT w.id, w.title_query, w.target_price, g.game_id, g.title, g.thumb,
               s.store_name, d.cheapshark_deal_id, MIN(d.sale_price), d.normal_price,
               d.discount_pct, {AT_LOW}
        FROM watchlist w
        JOIN games g ON title_matches(w.title_query, g.title)
        JOIN deals d ON d.game_id = g.game_id
        JOIN stores s ON d.store_id = s.store_id
        WHERE {LATEST} AND d.sale_price <= w.target_price
        GROUP BY w.id, g.game_id
        ORDER BY MIN(d.sale_price)
    """).fetchall()
    keys = ["watch_id", "watching", "target_price", "game_id", "title", "thumb", "store_name",
            "deal_id", "sale_price", "normal_price", "discount_pct", "at_historical_low"]
    return [dict(zip(keys, row)) for row in rows]


def pending_alerts(conn):
    """Hits that haven't been alerted yet, or have dropped below the last alerted price."""
    hits = current_hits(conn)
    current = {(h["watch_id"], h["game_id"]) for h in hits}

    sent = {}
    for watch_id, game_id, price in conn.execute("SELECT watch_id, game_id, price FROM alerts_sent").fetchall():
        if (watch_id, game_id) in current:
            sent[(watch_id, game_id)] = price
        else:
            # Back above target, so the next drop should alert again
            conn.execute("DELETE FROM alerts_sent WHERE watch_id = ? AND game_id = ?", (watch_id, game_id))
    conn.commit()

    return [
        h for h in hits
        if (h["watch_id"], h["game_id"]) not in sent
        or h["sale_price"] < sent[(h["watch_id"], h["game_id"])] - 0.001
    ]


def mark_sent(conn, alerts):
    now = datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        """
        INSERT INTO alerts_sent (watch_id, game_id, price, sent_at) VALUES (?, ?, ?, ?)
        ON CONFLICT (watch_id, game_id) DO UPDATE SET price = excluded.price, sent_at = excluded.sent_at
        """,
        [(a["watch_id"], a["game_id"], a["sale_price"], now) for a in alerts],
    )
    conn.commit()
