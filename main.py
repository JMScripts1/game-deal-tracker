# Command-line entry point for the game deal tracker

import argparse
import sys

import requests

import queries
import watchlist
from db_setup import DB_PATH, get_connection, setup_database
from fetch_and_store import fetch_and_store, sync_stores
from run import fetch_and_alert, start_scheduler


def show(title, df):
    print(f"=== {title} ===")
    if df.empty:
        print("No results. Run `python main.py fetch` to collect deals first.")
    else:
        print(df.to_string(index=False))
    print()


def cmd_init(args, conn):
    setup_database(conn)
    count = sync_stores(conn)
    print(f"Database ready at {DB_PATH} with {count} stores.")


def cmd_fetch(args, conn):
    if args.no_alerts:
        fetch_and_store(pages=args.pages)
    else:
        fetch_and_alert(pages=args.pages)


def cmd_top(args, conn):
    show(f"Top {args.limit} deals by discount", queries.top_deals(conn, args.limit))


def cmd_stores(args, conn):
    show("Deals by store", queries.deals_by_store(conn))


def cmd_history(args, conn):
    show(f"Price history for '{args.title}'", queries.price_history(conn, args.title))


def cmd_lows(args, conn):
    show("Currently at their lowest tracked price", queries.all_time_lows(conn, args.limit))


def cmd_watch(args, conn):
    if args.action == "add":
        if args.price is None:
            sys.exit("A target price is required: python main.py watch add \"Title\" 9.99")
        watchlist.add(conn, args.title, args.price)
        print(f"Watching '{args.title}' at ${args.price:.2f} or less.")
    elif args.action == "remove":
        removed = watchlist.remove(conn, args.title)
        print(f"Removed '{args.title}'." if removed else f"'{args.title}' wasn't on the watchlist.")
    elif args.action == "list":
        rows = watchlist.entries(conn)
        if not rows:
            print("Watchlist is empty.")
        for title, price, added in rows:
            print(f"{title:<40} ${price:>7.2f}   added {added}")
    elif args.action == "check":
        show("Watchlist alerts", queries.watchlist_hits(conn))


def cmd_schedule(args, conn):
    conn.close()
    start_scheduler(hours=args.hours, pages=args.pages)


def build_parser():
    parser = argparse.ArgumentParser(description="Track PC game deals from CheapShark.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database and load the store list").set_defaults(func=cmd_init)

    p = sub.add_parser("fetch", help="fetch a snapshot of current deals")
    p.add_argument("--pages", type=int, default=1, help="pages of 60 deals to fetch (default 1)")
    p.add_argument("--no-alerts", action="store_true", help="skip the watchlist check")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("top", help="biggest discounts in the latest snapshot")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_top)

    sub.add_parser("stores", help="deal summary per store").set_defaults(func=cmd_stores)

    p = sub.add_parser("history", help="price history for a title")
    p.add_argument("title")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("lows", help="deals at their lowest tracked price")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_lows)

    p = sub.add_parser("watch", help="manage the price watchlist")
    p.add_argument("action", choices=["add", "remove", "list", "check"])
    p.add_argument("title", nargs="?")
    p.add_argument("price", nargs="?", type=float)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("schedule", help="fetch on a repeating interval")
    p.add_argument("--hours", type=float, default=6)
    p.add_argument("--pages", type=int, default=1)
    p.set_defaults(func=cmd_schedule)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "watch" and args.action in ("add", "remove") and not args.title:
        parser.error(f"watch {args.action} needs a title")

    conn = get_connection()
    try:
        setup_database(conn)
        args.func(args, conn)
    except requests.RequestException as e:
        sys.exit(f"Could not reach the CheapShark API: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
