# Thin wrapper around the CheapShark API (https://apidocs.cheapshark.com)

import requests

BASE_URL = "https://www.cheapshark.com/api/1.0"
TIMEOUT = 15

# CheapShark rejects requests without a descriptive User-Agent
HEADERS = {"User-Agent": "game-deal-tracker/1.0 (+https://github.com/JMScripts1/game-deal-tracker)"}


def _get(endpoint, params=None):
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_deals(page_size=60, upper_price=60, sort_by="DealRating", page_number=0):
    """Fetch one page of current deals."""
    params = {
        "pageSize": page_size,
        "upperPrice": upper_price,
        "sortBy": sort_by,
        "pageNumber": page_number,
    }
    return _get("deals", params)


def get_stores():
    """Fetch the list of stores CheapShark tracks."""
    return _get("stores")


if __name__ == "__main__":
    deals = get_deals()
    print(f"Fetched {len(deals)} deals.")
    if deals:
        print(deals[0])
