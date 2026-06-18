# running this file will start the scheduler to fetch and store game deals every 6 hours


import schedule
import time
from fetch_and_store import fetch_and_store

fetch_and_store()  # run immediately on start

schedule.every(6).hours.do(fetch_and_store)

print("Scheduler running — fetching every 6 hours. Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(60)