# Runs fetch_and_store on a fixed interval and sends watchlist alerts after each fetch

import time

import requests
import schedule
from dotenv import load_dotenv

from alerts import mark_sent, pending_alerts
from db_setup import get_connection
from fetch_and_store import fetch_and_store
from notify import notify


def fetch_and_alert(pages=1):
    try:
        fetch_and_store(pages=pages)
    except requests.RequestException as e:
        # Don't let a temporary API failure kill the scheduler
        print(f"Fetch failed: {e}")
        return

    conn = get_connection()
    try:
        alerts = pending_alerts(conn)
        # Only remember alerts that were delivered, so failed ones retry next fetch
        if alerts and notify(alerts):
            mark_sent(conn, alerts)
    finally:
        conn.close()


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
    load_dotenv()
    start_scheduler()
