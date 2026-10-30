# Watchlist management: track titles and get alerted when they drop below a target price

from datetime import datetime


def add(conn, title_query, target_price):
    """Add a title to the watchlist, or update its target price if it's already there."""
    conn.execute(
        """
        INSERT INTO watchlist (title_query, target_price, added_at) VALUES (?, ?, ?)
        ON CONFLICT (title_query) DO UPDATE SET target_price = excluded.target_price
        """,
        (title_query, target_price, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def remove(conn, title_query):
    """Remove a title from the watchlist. Returns True if something was removed."""
    cursor = conn.execute("DELETE FROM watchlist WHERE title_query = ?", (title_query,))
    conn.commit()
    return cursor.rowcount > 0


def entries(conn):
    return conn.execute(
        "SELECT title_query, target_price, added_at FROM watchlist ORDER BY title_query"
    ).fetchall()
