# Fetches and stores game deal data from the CheapShark API into a SQLite database.


# This script combines the functionality of fetching data from the API and storing it in the database.
# It uses the functions defined in fetch.py to get the data and then inserts it into the SQLite database defined in db_setup.py.
import sqlite3
import requests
from fetch import get_deals, get_stores
from datetime import datetime

# Connect to the SQLite database
BASE_URL = "https://www.cheapshark.com/api/1.0"

# Function to fetch deals from the API
def get_deals(page_size=60):
    response = requests.get(
        f"{BASE_URL}/deals",
        params={"pageSize": page_size, "sortBy": "DealRating"},
    )
    response.raise_for_status()  # Check if the request was successful
    return response.json()

# Function to fetch stores from the API
def fetch_and_store():
    print(f"Fetching at {datetime.now().strftime('%H:%M:%S')}...")
    deals = get_deals()
    # Store deals in the database (implementation for storing in SQLite would go here)
    fetched_at = datetime.now().isoformat()
    conn = sqlite3.connect("deals.db")
    cursor = conn.cursor()
    
    games_added = 0
    deals_added = 0
    # Insert stores into the database
    for deal in deals:
        # Insert game into games table
        cursor.execute("""
            INSERT OR IGNORE INTO games (game_id, title, cheapest_ever) 
            VALUES (?, ?, ?)
        """, (deal['gameID'], deal['title'], float(deal["salePrice"])))
        
        if cursor.rowcount > 0:
            games_added += 1
            
            
    # Insert deal snapshot into deals table
        cursor.execute("""
            INSERT INTO deals 
            (cheapshark_deal_id, game_id, store_id, sale_price, 
             normal_price, discount_pct, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            deal["dealID"],
            deal["gameID"],
            deal["storeID"],
            float(deal["salePrice"]),
            float(deal["normalPrice"]),
            float(deal["savings"]),
            fetched_at
        ))
        deals_added += 1
# Commit and close the database connection
    conn.commit()
    conn.close()
    print(f"Done — {games_added} new games, {deals_added} snapshots stored.")
# Example usage
if __name__ == "__main__":
    fetch_and_store()
        