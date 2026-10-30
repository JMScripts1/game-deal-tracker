# Read-only reports over the deals database. Each function returns a pandas DataFrame.

import pandas as pd

# Most reports look at the most recent fetch only, so a deal isn't counted once per snapshot
LATEST = "d.fetched_at = (SELECT MAX(fetched_at) FROM deals)"

# On sale and at or below the historical low. Prices are stored as floats, hence the
# small tolerance. The discount check stops never-discounted games counting as lows.
AT_LOW = "d.discount_pct > 0 AND d.sale_price <= g.cheapest_ever + 0.001"


def top_deals(conn, limit=10):
    """Biggest discounts in the latest snapshot."""
    return pd.read_sql_query(f"""
        SELECT g.title, s.store_name, d.sale_price, d.normal_price,
               ROUND(d.discount_pct, 1) AS discount_pct,
               g.cheapest_ever AS historical_low
        FROM deals d
        JOIN games g ON d.game_id = g.game_id
        JOIN stores s ON d.store_id = s.store_id
        WHERE {LATEST} AND d.discount_pct > 0
        ORDER BY d.discount_pct DESC, d.sale_price ASC
        LIMIT ?
    """, conn, params=(limit,))


def deals_by_store(conn):
    """Deal count, average discount and cheapest deal per store in the latest snapshot."""
    return pd.read_sql_query(f"""
        SELECT s.store_name,
               COUNT(*) AS deal_count,
               ROUND(AVG(d.discount_pct), 1) AS avg_discount,
               ROUND(MIN(d.sale_price), 2) AS cheapest_deal
        FROM deals d
        JOIN stores s ON d.store_id = s.store_id
        WHERE {LATEST} AND d.discount_pct > 0
        GROUP BY s.store_id
        ORDER BY deal_count DESC
    """, conn)


def price_history(conn, title):
    """Every recorded price for games whose title contains `title`."""
    return pd.read_sql_query("""
        SELECT g.title, s.store_name, d.sale_price,
               ROUND(d.discount_pct, 1) AS discount_pct, d.fetched_at
        FROM deals d
        JOIN games g ON d.game_id = g.game_id
        JOIN stores s ON d.store_id = s.store_id
        WHERE g.title LIKE ?
        ORDER BY g.title, d.fetched_at ASC
    """, conn, params=(f"%{title}%",))


def all_time_lows(conn, limit=20):
    """Deals in the latest snapshot that match or beat the game's historical low."""
    return pd.read_sql_query(f"""
        SELECT g.title, s.store_name, d.sale_price, d.normal_price,
               ROUND(d.discount_pct, 1) AS discount_pct,
               g.cheapest_ever_date AS historical_low_date
        FROM deals d
        JOIN games g ON d.game_id = g.game_id
        JOIN stores s ON d.store_id = s.store_id
        WHERE {LATEST} AND {AT_LOW}
        ORDER BY d.discount_pct DESC
        LIMIT ?
    """, conn, params=(limit,))


def watchlist_hits(conn):
    """Latest deals that match a watchlist entry and are at or below its target price."""
    return pd.read_sql_query(f"""
        SELECT w.title_query AS watching, w.target_price, g.title,
               s.store_name, d.sale_price
        FROM watchlist w
        JOIN games g ON title_matches(w.title_query, g.title)
        JOIN deals d ON d.game_id = g.game_id
        JOIN stores s ON d.store_id = s.store_id
        WHERE {LATEST} AND d.sale_price <= w.target_price
        ORDER BY d.sale_price ASC
    """, conn)
