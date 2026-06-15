# calls get stores and get deals from fetch.py and fills the database with the data


import sqlite3
from fetch import get_deals, get_stores
conn =  sqlite3.connect("deals.db")
cursor = conn.cursor()


stores = get_stores()
for store in stores:
    cursor.execute("INSERT OR IGNORE INTO stores (store_id, store_name) VALUES (?, ?)", (store['storeID'], store['storeName']))
    
    
# commit and close after processing all stores
conn.commit()
conn.close()
print(f"Inserted {len(stores)} stores into the database.")