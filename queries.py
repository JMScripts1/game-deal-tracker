# Verifying that the queries are correct and that they return the expected results.
# This file contains the queries that are used to extract data from the database. It also contains the code to execute the queries and return the results as a pandas DataFrame.

import sqlite3
import pandas as pd

DB_PATH = 'deals.db'

# Establishing a connection to the database
conn = sqlite3.connect(DB_PATH)

# Verify required tables exist
required_tables = {'deals', 'games', 'stores'}
existing_tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
missing_tables = required_tables - existing_tables
if missing_tables:
    raise RuntimeError(f"Missing required tables in {DB_PATH}: {', '.join(sorted(missing_tables))}")

# Top 10 dealers by discount currently
top_deals = pd.read_sql_query("""SELECT g.title, s.store_name, d.sale_price, d.normal_price, ROUND(d.discount_pct, 1) as discount_pct, d.fetched_at
                               FROM deals d
                               JOIN games g ON d.game_id = g.game_id
                               JOIN stores s ON d.store_id = s.store_id
                               ORDER BY d.discount_pct DESC
                               LIMIT 10""", conn)

print("=== Top 10 deals by discount ===")
print(top_deals.to_string())
print()

# Deals per store with average discount
by_store = pd.read_sql_query("""
    SELECT 
        s.store_name,
        COUNT(*) AS deal_count,
        ROUND(AVG(d.discount_pct), 1) AS avg_discount,
        ROUND(MIN(d.sale_price), 2) AS cheapest_deal
    FROM deals d
    JOIN stores s ON d.store_id = s.store_id
    GROUP BY s.store_id
    ORDER BY deal_count DESC
""", conn)
# This query retrieves the number of deals, average discount percentage, and cheapest deal for each store. It groups the results by store and orders them by the number of deals in descending order.
print("=== Deals by store ===")
print(by_store.to_string())
print()
# Price history for a specific game (e.g., "Cyberpunk 2077")
history = pd.read_sql_query("""
    SELECT 
        g.title,
        d.sale_price,
        d.discount_pct,
        d.fetched_at
    FROM deals d
    JOIN games g ON d.game_id = g.game_id
    WHERE g.title LIKE '%Cyberpunk%'
    ORDER BY d.fetched_at ASC
""", conn)
# retrieves the price history for a specific game (in this case, "Cyberpunk 2077"). It joins the deals and games tables, filters for the game title, and orders the results by the date they were fetched in ascending order.
print("=== Price history ===")
print(history.to_string())

conn.close()
