# Runs fetch_and_store on a fixed interval and prints watchlist alerts after each fetch

import time

import requests
import schedule

from db_setup import get_connection
from fetch_and_store import fetch_and_store
from queries import watchlist_hits


def fetch_and_alert(pages=1):
    try:
        fetch_and_store(pages=pages)
    except requests.RequestException as e:
        # Don't let a temporary API failure kill the scheduler
        print(f"Fetch failed: {e}")
        return

    conn = get_connection()
    try:
        hits = watchlist_hits(conn)
    finally:
        conn.close()
    if not hits.empty:
        print("=== Watchlist alerts ===")
        print(hits.to_string(index=False))


def start_scheduler(hours=6, pages=1):
    fetch_and_alert(pages)  # run immediately on start
    schedule.every(hours).hours.do(fetch_and_alert, pages=pages)

    print(f"Scheduler running, fetching every {hours} hours. Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
