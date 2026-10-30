# Game Deal Tracker

A command-line tool that collects PC game deals from the [CheapShark API](https://apidocs.cheapshark.com), stores timestamped price snapshots in SQLite, and turns them into reports: top discounts, per-store summaries, price history, all-time lows, and watchlist alerts.

Every fetch is stored as its own snapshot instead of overwriting the last one. That gives you a price history for each game, so you can tell a real low from a routine "sale".

## Features

- **Deal collection**: pulls current deals from more than 30 storefronts (Steam, GOG, Epic, Humble, Fanatical and others) through CheapShark.
- **Price history**: every fetch is saved with a timestamp, so you can see how a game's price has moved over time.
- **Lowest-price tracking**: records the cheapest price seen for each game and flags deals that match it.
- **Watchlist alerts**: set a target price for any title and get an alert when a deal reaches it.
- **Scheduled fetching**: a built-in scheduler collects snapshots on an interval you choose.
- **Store summaries**: deal counts, average discount, and cheapest deal for each store.

## Requirements

- Python 3.10 or newer
- An internet connection (CheapShark needs no API key)

## Installation

```bash
git clone https://github.com/JMScripts1/game-deal-tracker.git
cd game-deal-tracker

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## Quick start

```bash
python main.py init          # create the database and load the store list
python main.py fetch         # take your first snapshot of current deals
python main.py top           # see the biggest discounts
```

## Usage

| Command | Description |
| --- | --- |
| `python main.py init` | Create the database and sync store names from CheapShark. |
| `python main.py fetch [--pages N] [--no-alerts]` | Fetch `N` pages of 60 deals (default 1) and store them as one snapshot. Watchlist alerts print afterwards unless you pass `--no-alerts`. |
| `python main.py top [--limit N]` | Show the biggest discounts in the latest snapshot. |
| `python main.py stores` | Show deal count, average discount, and cheapest deal for each store. |
| `python main.py history "<title>"` | Show every recorded price for games whose title contains the search text. |
| `python main.py lows [--limit N]` | Show deals that are at the lowest price the tracker has recorded. |
| `python main.py watch add "<title>" <price>` | Watch a title and alert when it reaches the target price. Adding a title that is already watched updates its target. |
| `python main.py watch remove "<title>"` | Stop watching a title. |
| `python main.py watch list` | List watched titles and their target prices. |
| `python main.py watch check` | Check the latest snapshot against the watchlist. |
| `python main.py schedule [--hours H] [--pages N]` | Fetch once right away, then again every `H` hours (default 6), with alerts after each fetch. Press `Ctrl+C` to stop. |

### Example

```text
$ python main.py watch add "Divinity" 10
Watching 'Divinity' at $10.00 or less.

$ python main.py fetch --pages 2
Fetching at 13:59:34...
Done: 52 new games, 120 snapshots stored.
=== Watchlist alerts ===
watching  target_price                                      title store_name  sale_price
Divinity          10.0  Divinity: Original Sin - Enhanced Edition        GOG        5.99

$ python main.py top --limit 3
=== Top 3 deals by discount ===
                                 title       store_name  sale_price  normal_price  discount_pct
                     Sorry Were Closed Epic Games Store        0.00         24.99         100.0
                           MAFIA HOTEL Epic Games Store        0.00          1.99         100.0
Suicide Squad: Kill the Justice League Epic Games Store        3.49         69.99          95.0
```

## Configuration

The database is written to `deals.db` in the current directory. Set the `DEALS_DB` environment variable to use a different path:

```bash
# macOS / Linux
export DEALS_DB=/path/to/deals.db
# Windows (PowerShell)
$env:DEALS_DB = "C:\path\to\deals.db"
```

## Project structure

```text
├── main.py              # CLI entry point (argparse subcommands)
├── fetch.py             # CheapShark API client
├── fetch_and_store.py   # Fetches deals and writes snapshots to SQLite
├── db_setup.py          # Connection helper and schema
├── queries.py           # Reports, each returned as a pandas DataFrame
├── watchlist.py         # Watchlist add / remove / list
├── run.py               # Interval scheduler with alerting
├── requirements.txt
└── tests/
    └── test_tracker.py
```

## Data model

| Table | Purpose |
| --- | --- |
| `stores` | CheapShark store IDs and names. |
| `games` | One row per game, including `cheapest_ever`: the lowest sale price the tracker has recorded. |
| `deals` | One row per deal per fetch: sale price, normal price, discount, and `fetched_at` timestamp. |
| `watchlist` | Watched title searches and their target prices. |

Reports such as `top`, `stores`, `lows`, and watchlist checks use only the most recent snapshot, so a deal is counted once no matter how many fetches have run. `history` uses every snapshot.

## Running tests

```bash
pytest
```

The tests use an in-memory SQLite database with sample data, so they don't call the live API.

## Notes

- `cheapest_ever` is the lowest price **this tracker has recorded**, not CheapShark's historical low. It gets more meaningful the longer the scheduler runs.
- CheapShark is a free, rate-limited service. The default 6-hour interval stays well within its limits; please don't fetch aggressively.
- Deal data is provided by [CheapShark](https://www.cheapshark.com). This project is not affiliated with CheapShark or any of the storefronts it tracks.
