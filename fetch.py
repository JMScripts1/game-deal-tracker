# Fetching from API

import requests 

BASE_URL = "https://www.cheapshark.com/api/1.0"

# Function to fetch deals from the API

def get_deals(page_size=60, upper_price=60, sort_by="DealRating"):

    params = {
    "pageSize": page_size,
    "upperPrice": upper_price,
    "sortBy": sort_by,
    
    
}
    response = requests.get(f"{BASE_URL}/deals", params=params)
    response.raise_for_status()  # Check if the request was successful
    return response.json()

# Function to fetch stores from the API

def get_stores():
    response = requests.get(f"{BASE_URL}/stores")
    response.raise_for_status()  # Check if the request was successful IMPORTANT.
    return response.json()
if __name__ == "__main__":
    deals = get_deals()
    print(f"Fetched {len(deals)} deals.")
    print(deals[0])  # Print the first deal as an example
    
    