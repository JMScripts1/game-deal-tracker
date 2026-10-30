# Streamlit dashboard for browsing deals, price history and the watchlist.
# Run with: streamlit run dashboard.py

from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import queries  # noqa: E402
import watchlist  # noqa: E402
from alerts import current_hits  # noqa: E402
from db_setup import get_connection, setup_database  # noqa: E402
from notify import deal_url  # noqa: E402
from run import fetch_and_alert  # noqa: E402

st.set_page_config(page_title="Game Deal Tracker", page_icon="🎮", layout="wide")

conn = get_connection()
setup_database(conn)


def money(value):
    return f"${value:,.2f}"


# --- Sidebar: fetching and watchlist management -----------------------------

with st.sidebar:
    st.header("Fetch deals")
    pages = st.number_input("Pages of 60 deals", min_value=1, max_value=10, value=1)
    if st.button("Fetch now", type="primary", width="stretch"):
        with st.spinner("Fetching from CheapShark..."):
            try:
                fetch_and_alert(pages=int(pages))
                st.toast("Snapshot saved")
            except requests.RequestException as e:
                st.error(f"Fetch failed: {e}")

    st.divider()
    st.header("Watchlist")
    with st.form("add_watch", clear_on_submit=True):
        title = st.text_input("Title", placeholder="e.g. Hades")
        target = st.number_input("Target price ($)", min_value=0.0, value=10.0, step=1.0)
        if st.form_submit_button("Watch", width="stretch") and title.strip():
            watchlist.add(conn, title.strip(), target)
            st.toast(f"Watching '{title.strip()}' at {money(target)}. It'll be looked up on the next fetch.")

    entries = watchlist.entries(conn)
    for query, price, _ in entries:
        left, right = st.columns([4, 1])
        left.write(f"**{query}** at {money(price)}")
        if right.button("✕", key=f"remove_{query}", help=f"Stop watching {query}"):
            watchlist.remove(conn, query)
            st.rerun()


# --- Header and headline numbers ---------------------------------------------

st.title("🎮 Game Deal Tracker")
info = queries.summary(conn)

if not info["last_fetch"]:
    st.info("No deals yet. Click **Fetch now** in the sidebar to take your first snapshot.")
    st.stop()

last_fetch = datetime.fromisoformat(info["last_fetch"])
st.caption(f"Last fetched {last_fetch:%b %d, %Y at %H:%M} · "
           f"{info['games']:,} games tracked across {info['snapshots']:,} "
           f"snapshot{'s' if info['snapshots'] != 1 else ''} · "
           f"Data from [CheapShark](https://www.cheapshark.com)")

deals = queries.latest_deals(conn)
deals["link"] = deals["deal_id"].map(deal_url)

# One row per watched game, at its cheapest store, matching what alerts report
hits = pd.DataFrame(current_hits(conn), columns=[
    "watching", "target_price", "title", "thumb", "store_name", "deal_id",
    "sale_price", "normal_price", "discount_pct", "at_historical_low"])
hits["link"] = hits["deal_id"].map(deal_url)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Deals in latest snapshot", f"{len(deals):,}")
c2.metric("Average discount", f"{deals['discount_pct'].mean():.0f}%" if len(deals) else "–")
c3.metric("At historical low", f"{int(deals['at_historical_low'].sum()):,}")
c4.metric("Watchlist matches", f"{len(hits):,}")

DEAL_COLUMNS = {
    "thumb": st.column_config.ImageColumn("", width="small"),
    "title": st.column_config.TextColumn("Game", width="large"),
    "store_name": "Store",
    "sale_price": st.column_config.NumberColumn("Price", format="$%.2f"),
    "normal_price": st.column_config.NumberColumn("Normally", format="$%.2f"),
    "discount_pct": st.column_config.ProgressColumn("Discount", format="%.0f%%", min_value=0, max_value=100),
    "historical_low": st.column_config.NumberColumn("Historical low", format="$%.2f"),
    "historical_low_date": "Low since",
    "link": st.column_config.LinkColumn("", display_text="View deal"),
}


def deal_table(df):
    st.dataframe(df[[c for c in DEAL_COLUMNS if c in df.columns]], column_config=DEAL_COLUMNS,
                 hide_index=True, width="stretch")


tab_deals, tab_lows, tab_history, tab_stores, tab_watch = st.tabs(
    ["Top deals", "Historical lows", "Price history", "Stores", "Watchlist"])

# --- Top deals ---------------------------------------------------------------

with tab_deals:
    f1, f2, f3 = st.columns([2, 1, 1])
    stores = f1.multiselect("Stores", sorted(deals["store_name"].unique()), placeholder="All stores")
    max_price = f2.slider("Max price", 0.0, float(max(deals["sale_price"].max(), 1)),
                          float(max(deals["sale_price"].max(), 1)), step=1.0, format="$%.0f")
    min_discount = f3.slider("Min discount", 0, 100, 0, step=5, format="%d%%")

    filtered = deals[(deals["sale_price"] <= max_price) & (deals["discount_pct"] >= min_discount)]
    if stores:
        filtered = filtered[filtered["store_name"].isin(stores)]
    st.caption(f"{len(filtered):,} of {len(deals):,} deals")
    deal_table(filtered)

# --- Historical lows -----------------------------------------------------------

with tab_lows:
    lows = deals[deals["at_historical_low"] == 1]
    st.caption("Deals that match or beat the lowest price CheapShark has ever recorded for the game.")
    if lows.empty:
        st.write("Nothing is at its historical low in the latest snapshot.")
    else:
        deal_table(lows)

# --- Price history -------------------------------------------------------------

with tab_history:
    search = st.text_input("Search for a game", placeholder="e.g. Baldur's Gate", key="history_search")
    if search:
        history = queries.price_history(conn, search)
        if history.empty:
            st.write(f"No price history for '{search}'.")
        else:
            game = st.selectbox("Game", sorted(history["title"].unique()))
            game_history = history[history["title"] == game].copy()
            game_history["fetched_at"] = pd.to_datetime(game_history["fetched_at"])

            low = conn.execute("SELECT cheapest_ever FROM games WHERE title = ?", (game,)).fetchone()[0]
            lines = alt.Chart(game_history).mark_line(point=True, interpolate="step-after").encode(
                x=alt.X("fetched_at:T", title=None),
                y=alt.Y("sale_price:Q", title="Price ($)", scale=alt.Scale(zero=True)),
                color=alt.Color("store_name:N", title="Store"),
                tooltip=[alt.Tooltip("store_name", title="Store"),
                         alt.Tooltip("sale_price", title="Price", format="$.2f"),
                         alt.Tooltip("discount_pct", title="Discount %"),
                         alt.Tooltip("fetched_at:T", title="Fetched", format="%b %d %H:%M")],
            )
            chart = lines
            if low is not None:
                rule = alt.Chart(pd.DataFrame({"low": [low]})).mark_rule(strokeDash=[6, 4], color="gray").encode(
                    y="low:Q", tooltip=[alt.Tooltip("low", title="Historical low", format="$.2f")])
                chart = lines + rule
                st.caption(f"Dashed line: historical low of {money(low)}")
            st.altair_chart(chart, width="stretch")

            if game_history["fetched_at"].nunique() == 1:
                st.caption("Only one snapshot so far. The chart fills in as more fetches run.")

# --- Stores ----------------------------------------------------------------------

with tab_stores:
    by_store = queries.deals_by_store(conn)
    left, right = st.columns(2)
    with left:
        st.subheader("Deals per store")
        st.altair_chart(alt.Chart(by_store).mark_bar().encode(
            x=alt.X("deal_count:Q", title="Deals"),
            y=alt.Y("store_name:N", sort="-x", title=None),
            tooltip=["store_name", "deal_count"],
        ), width="stretch")
    with right:
        st.subheader("Average discount")
        st.altair_chart(alt.Chart(by_store).mark_bar().encode(
            x=alt.X("avg_discount:Q", title="Average discount (%)", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("store_name:N", sort="-x", title=None),
            tooltip=["store_name", "avg_discount"],
        ), width="stretch")

# --- Watchlist -------------------------------------------------------------------

with tab_watch:
    if not entries:
        st.write("Your watchlist is empty. Add a game in the sidebar.")
    elif hits.empty:
        st.write("None of your watched games are at or below their target price right now.")
    else:
        st.caption("Watched games at or below your target price in the latest snapshot, at the cheapest store.")
        columns = {
            "thumb": DEAL_COLUMNS["thumb"],
            "title": DEAL_COLUMNS["title"],
            "watching": "Watching",
            "target_price": st.column_config.NumberColumn("Target", format="$%.2f"),
            "store_name": "Store",
            "sale_price": DEAL_COLUMNS["sale_price"],
            "normal_price": DEAL_COLUMNS["normal_price"],
            "at_historical_low": st.column_config.CheckboxColumn("Historical low"),
            "link": DEAL_COLUMNS["link"],
        }
        st.dataframe(hits[list(columns)], column_config=columns, hide_index=True, width="stretch")
