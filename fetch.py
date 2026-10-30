# Thin wrapper around the CheapShark API (https://apidocs.cheapshark.com)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.cheapshark.com/api/1.0"
TIMEOUT = 30
GAMES_BATCH_SIZE = 25  # max ids CheapShark accepts per /games lookup

# CheapShark rejects requests without a descriptive User-Agent
HEADERS = {"User-Agent": "game-deal-tracker/1.0 (+https://github.com/JMScripts1/game-deal-tracker)"}

# CheapShark is occasionally slow and rate-limits bursts, so retry with backoff
# (honouring Retry-After on 429s) instead of failing the whole fetch
session = requests.Session()
session.headers.update(HEADERS)
session.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
)))


def _get(endpoint, params=None):
    response = session.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
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


def search_games(title, limit=10):
    """Search games by title. CheapShark's matching is fuzzy, so callers should filter."""
    return _get("games", {"title": title, "limit": limit})


def get_games(game_ids):
    """Look up games by id. Returns {game_id: {info, cheapestPriceEver, deals}}."""
    game_ids = sorted(game_ids)
    games = {}
    for i in range(0, len(game_ids), GAMES_BATCH_SIZE):
        batch = game_ids[i:i + GAMES_BATCH_SIZE]
        result = _get("games", {"ids": ",".join(batch)})
        # A single unknown id comes back as an empty list instead of a dict
        if isinstance(result, dict):
            games.update(result)
    return games


if __name__ == "__main__":
    deals = get_deals()
    print(f"Fetched {len(deals)} deals.")
    if deals:
        print(deals[0])
