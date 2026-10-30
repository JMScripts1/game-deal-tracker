# Streamlit dashboard for browsing deals, price history and the watchlist.
# Run with: streamlit run dashboard.py

import html
import re
from datetime import datetime
from pathlib import Path

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

st.set_page_config(page_title="Game Deal Tracker", page_icon=":material/sell:", layout="wide")

conn = get_connection()
setup_database(conn)

ACCENT = "#3ccf80"
MUTED = "#9ba2a9"
LINE = "#262b30"
# Accent first, then neutrals, so multi-store charts stay on palette (matches config.toml)
SERIES = ["#3ccf80", "#a3adb8", "#2e8f5a", "#e1e5e8", "#6b7580", "#8fe3b5"]
PAGE_SIZE = 24

# Phosphor icons, inlined from the sprite in ./static so they inherit text colour
_SPRITE = (Path(__file__).parent / "static" / "icons.svg").read_text(encoding="utf-8")
ICONS = {name: (box, body) for name, box, body in
         re.findall(r'<symbol id="([^"]+)" viewBox="([^"]+)"[^>]*>(.*?)</symbol>', _SPRITE, re.S)}


def icon(name, cls="ico"):
    box, body = ICONS[name]
    return f'<svg class="{cls}" viewBox="{box}" fill="currentColor" aria-hidden="true">{body}</svg>'


def money(value):
    # Written as an entity because Streamlit markdown treats $...$ as maths
    return "Free" if value == 0 else f"&#36;{value:,.2f}"


def esc(text):
    return html.escape(str(text))


def art_style(row):
    """Steam's 460x215 header art when we know the app id, layered over the store thumbnail."""
    layers = []
    if isinstance(row.get("steam_app_id"), str) and row["steam_app_id"]:
        layers.append(f"url('https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/"
                      f"{row['steam_app_id']}/header.jpg')")
    if isinstance(row.get("thumb"), str) and row["thumb"]:
        layers.append(f"url('{row['thumb']}')")
    return f"background-image:{','.join(layers)};" if layers else ""


def time_ago(moment):
    seconds = (datetime.now() - moment).total_seconds()
    if seconds < 90:
        return "just now"
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"


def nice_date(iso_date):
    """', on Jul 30, 2026' for an ISO date, or nothing when the date is unknown."""
    if not isinstance(iso_date, str) or not iso_date:
        return ""
    day = datetime.fromisoformat(iso_date)
    return f", on {day:%b} {day.day}, {day.year}"


def best_per_game(df):
    """One row per game at its cheapest store, with how many stores carry it."""
    if df.empty:
        return df.assign(store_count=[])
    counts = df.groupby("game_id").size().rename("store_count")
    best = df.sort_values(["sale_price", "discount_pct"], ascending=[True, False]).drop_duplicates("game_id")
    return best.join(counts, on="game_id")


def html_block(markup):
    # Collapse whitespace so markdown never mistakes indented HTML for a code block
    st.markdown(re.sub(r"\s*\n\s*", " ", markup), unsafe_allow_html=True)


def chart_style(chart):
    return (chart.configure(background="transparent", font="Geist")
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor=LINE, domainColor=LINE,
                            tickColor=LINE, labelFontSize=12, titleFontSize=12, titleFontWeight=500)
            .configure_legend(labelColor=MUTED, titleColor=MUTED, labelFontSize=12, titleFontSize=12))


html_block("""
<style>
:root {
  --bg: #0d0f11; --surface: #14171a; --surface-2: #1a1e22; --line: #262b30;
  --text: #eceeef; --muted: #9ba2a9; --accent: #3ccf80; --accent-ink: #06210f; --accent-soft: #12281c;
}
/* Shape rule: containers 12px, controls 8px, price pills fully rounded */
[data-testid="stMainBlockContainer"] { padding-top: 2.2rem; max-width: 1400px; }
header[data-testid="stHeader"] { background: transparent; }
h1, h2, h3 { letter-spacing: -0.02em; }
button[data-baseweb="tab"] { font-size: 0.95rem; padding-inline: 2px; }
[data-baseweb="tab-list"] { gap: 26px; }
.ico { width: 1.1em; height: 1.1em; flex: none; vertical-align: -0.18em; }
.mono { font-variant-numeric: tabular-nums; }

.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
.brand { display: flex; align-items: center; gap: 12px; font-size: 1.35rem; font-weight: 650; letter-spacing: -0.02em; }
.brand .ico { color: var(--accent); width: 26px; height: 26px; }
.meta { color: var(--muted); font-size: 0.9rem; }

.hero { display: grid; grid-template-columns: minmax(0, 2.1fr) minmax(0, 1fr); gap: 20px; margin-bottom: 34px; }
.spot { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); background: var(--surface);
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.spot .art { min-height: 250px; }
.spot .info { padding: 26px 28px; display: flex; flex-direction: column; gap: 10px; }
.spot .label { color: var(--accent); font-weight: 600; font-size: 0.92rem; display: flex; align-items: center; gap: 8px; }
.spot h2 { margin: 0; padding: 0; font-size: 1.7rem; line-height: 1.15; font-weight: 650; }
.spot .price { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-top: 4px; }
.spot .now { font-size: 2.3rem; font-weight: 600; letter-spacing: -0.03em; }
.spot .note { color: var(--muted); font-size: 0.93rem; margin: 0; }
.spot .cta { margin-top: auto; align-self: flex-start; display: inline-flex; align-items: center; gap: 8px;
  background: var(--accent); color: var(--accent-ink) !important; text-decoration: none !important;
  font-weight: 600; padding: 10px 16px; border-radius: 8px; transition: transform .2s cubic-bezier(.16,1,.3,1); }
.spot .cta:hover { transform: translateY(-1px); }
.spot .cta:active { transform: scale(.98); }

.stats { display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }
.stat { flex: 1; padding: 18px 22px; display: flex; flex-direction: column; justify-content: center; }
.stat + .stat { border-top: 1px solid var(--line); }
.stat .num { font-size: 2rem; font-weight: 600; letter-spacing: -0.03em; line-height: 1.1; }
.stat .num.accent { color: var(--accent); }
.stat .what { color: var(--muted); font-size: 0.9rem; }

.was { color: var(--muted); text-decoration: line-through; }
.pill { display: inline-block; background: var(--accent-soft); color: var(--accent); font-weight: 600;
  font-size: 0.82rem; padding: 2px 9px; border-radius: 999px; }
.art { background-color: var(--surface-2); background-size: cover; background-position: center; }

.section-title { display: flex; align-items: baseline; justify-content: space-between; margin: 0 0 14px; }
.section-title h3 { margin: 0; padding: 0; font-size: 1.15rem; font-weight: 600; }
.section-title span { color: var(--muted); font-size: 0.9rem; }
.strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(250px, 280px); gap: 14px;
  overflow-x: auto; padding-bottom: 8px; margin-bottom: 30px; scroll-snap-type: x mandatory; }
.strip .card { scroll-snap-align: start; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 16px; margin-top: 6px; }
.card { display: flex; flex-direction: column; background: var(--surface); border: 1px solid var(--line);
  border-radius: 12px; overflow: hidden; color: var(--text) !important; text-decoration: none !important;
  transition: transform .25s cubic-bezier(.16,1,.3,1), border-color .2s; }
.card:hover { transform: translateY(-3px); border-color: #3a4148; }
.card .art { aspect-ratio: 460 / 215; }
.card .body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.card .title { font-weight: 600; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card .store { color: var(--muted); font-size: 0.85rem; }
.card .row { display: flex; align-items: baseline; gap: 8px; margin-top: auto; padding-top: 6px; flex-wrap: wrap; }
.card .now { font-size: 1.15rem; font-weight: 600; }
.card .was { font-size: 0.85rem; }
.card .low { color: var(--accent); font-size: 0.82rem; display: flex; align-items: center; gap: 6px; }
.card .target { color: var(--accent); font-size: 0.85rem; }

.watchrow { display: grid; grid-template-columns: 150px minmax(0, 1fr) auto; gap: 18px; align-items: center;
  padding: 14px 0; border-bottom: 1px solid var(--line); }
.watchrow .art { aspect-ratio: 460 / 215; border-radius: 8px; }
.watchrow .q { font-weight: 600; }
.watchrow .sub { color: var(--muted); font-size: 0.88rem; }
.watchrow .status { text-align: right; }
.watchrow .status .good { color: var(--accent); font-weight: 600; }
.watchrow .status .off { color: var(--muted); }
.watchrow a { color: var(--text) !important; }

.gamehead { display: flex; gap: 18px; align-items: center; margin: 10px 0 18px; }
.gamehead .art { width: 184px; aspect-ratio: 460 / 215; border-radius: 8px; flex: none; }
.gamehead .figs { display: flex; gap: 34px; flex-wrap: wrap; }
.gamehead .fig .num { font-size: 1.4rem; font-weight: 600; }
.gamehead .fig .what { color: var(--muted); font-size: 0.85rem; }

.empty { border: 1px dashed var(--line); border-radius: 12px; padding: 48px 32px; text-align: center; color: var(--muted); }
.empty .ico { width: 34px; height: 34px; color: var(--accent); margin-bottom: 10px; }
.empty h3 { color: var(--text); margin: 0 0 6px; padding: 0; font-size: 1.2rem; }

@media (max-width: 1100px) { .hero { grid-template-columns: 1fr; } .stats { flex-direction: row; } .stat + .stat { border-top: 0; border-left: 1px solid var(--line); } }
@media (max-width: 760px) {
  .spot { grid-template-columns: 1fr; } .spot .art { min-height: 0; aspect-ratio: 460 / 215; }
  .stats { flex-direction: column; } .stat + .stat { border-left: 0; border-top: 1px solid var(--line); }
  .watchrow { grid-template-columns: 96px minmax(0, 1fr); } .watchrow .status { grid-column: 2; text-align: left; }
}
@media (prefers-reduced-motion: reduce) { .card, .spot .cta { transition: none; } .card:hover { transform: none; } }
</style>
""")


def deal_card(row, extra=""):
    stores = f" +{row['store_count'] - 1} more" if row.get("store_count", 1) > 1 else ""
    low = (f'<div class="low">{icon("trend-down")}Lowest price ever</div>'
           if row.get("at_historical_low") else "")
    was = f'<span class="was mono">{money(row["normal_price"])}</span>' if row["discount_pct"] > 0 else ""
    pill = f'<span class="pill">-{row["discount_pct"]:.0f}%</span>' if row["discount_pct"] > 0 else ""
    return (f'<a class="card" href="{deal_url(row["deal_id"])}" target="_blank" rel="noopener">'
            f'<div class="art" style="{art_style(row)}"></div>'
            f'<div class="body"><div class="title">{esc(row["title"])}</div>'
            f'<div class="store">{esc(row["store_name"])}{stores}</div>{extra}{low}'
            f'<div class="row"><span class="now mono">{money(row["sale_price"])}</span>{was}{pill}</div>'
            f'</div></a>')


def card_grid(df, limit=None):
    rows = df.head(limit) if limit else df
    html_block('<div class="grid">' + "".join(deal_card(r) for _, r in rows.iterrows()) + "</div>")


def empty_state(icon_name, title, text):
    html_block(f'<div class="empty">{icon(icon_name)}<h3>{esc(title)}</h3><div>{text}</div></div>')


# --- Sidebar: fetching and watchlist management -----------------------------

with st.sidebar:
    st.subheader("Fetch deals")
    pages = st.number_input("Pages of 60 deals", min_value=1, max_value=10, value=1)
    if st.button("Fetch now", type="primary", icon=":material/refresh:", width="stretch"):
        with st.spinner("Fetching from CheapShark..."):
            try:
                fetch_and_alert(pages=int(pages))
                st.toast("Snapshot saved")
            except requests.RequestException as e:
                st.error(f"Fetch failed: {e}")

    st.divider()
    st.subheader("Watchlist")
    with st.form("add_watch", clear_on_submit=True):
        title = st.text_input("Game title", placeholder="e.g. Hades")
        target = st.number_input("Alert at or below ($)", min_value=0.0, value=10.0, step=1.0)
        if st.form_submit_button("Watch this game", width="stretch") and title.strip():
            watchlist.add(conn, title.strip(), target)
            st.toast(f"Watching '{title.strip()}'. It'll be looked up on the next fetch.")

    entries = watchlist.entries(conn)
    for query, price, _ in entries:
        left, right = st.columns([5, 1], vertical_alignment="center")
        left.markdown(f"**{esc(query)}**  \nat or below {money(price)}", unsafe_allow_html=True)
        if right.button("", icon=":material/close:", key=f"remove_{query}", help=f"Stop watching {query}"):
            watchlist.remove(conn, query)
            st.rerun()


# --- Header ------------------------------------------------------------------

info = queries.summary(conn)
meta = ""
if info["last_fetch"]:
    meta = (f"Updated {time_ago(datetime.fromisoformat(info['last_fetch']))}. "
            f"{info['games']:,} games tracked over {info['snapshots']:,} snapshot{'s' if info['snapshots'] != 1 else ''}.")
html_block(f'<div class="topbar"><div class="brand">{icon("tag")}Game Deal Tracker</div>'
           f'<div class="meta">{meta}</div></div>')

if not info["last_fetch"]:
    empty_state("arrows-clockwise", "No deals yet",
                "Click <b>Fetch now</b> in the sidebar to take your first snapshot. It only takes a few seconds.")
    st.stop()

deals = queries.latest_deals(conn)
games = best_per_game(deals)
hits = pd.DataFrame(current_hits(conn), columns=[
    "watching", "target_price", "game_id", "title", "thumb", "store_name", "deal_id",
    "sale_price", "normal_price", "discount_pct", "at_historical_low"])
# current_hits doesn't carry the Steam app id, so borrow it from the deal rows
hits = hits.merge(games[["game_id", "steam_app_id"]], on="game_id", how="left")

# --- Spotlight: the biggest saving, preferring games at their historical low --

if not games.empty:
    lows = games[games["at_historical_low"] == 1]
    pool = (lows if not lows.empty else games).assign(saving=lambda d: d["normal_price"] - d["sale_price"])
    pick = pool.sort_values(["saving", "discount_pct"], ascending=False).iloc[0]
    note = ("The lowest price this game has ever had." if pick["at_historical_low"]
            else "The biggest saving in the latest snapshot.")
    spotlight = (
        f'<div class="spot"><div class="art" style="{art_style(pick)}"></div><div class="info">'
        f'<div class="label">{icon("trend-down")}Biggest drop right now</div>'
        f'<h2>{esc(pick["title"])}</h2>'
        f'<div class="price"><span class="now mono">{money(pick["sale_price"])}</span>'
        f'<span class="was mono">{money(pick["normal_price"])}</span>'
        f'<span class="pill">-{pick["discount_pct"]:.0f}%</span></div>'
        f'<p class="note">At {esc(pick["store_name"])}. {note}</p>'
        f'<a class="cta" href="{deal_url(pick["deal_id"])}" target="_blank" rel="noopener">'
        f'View deal {icon("arrow-square-out")}</a></div></div>')
else:
    spotlight = '<div class="spot"><div class="info"><p class="note">No discounted deals in the latest snapshot.</p></div></div>'

stats = (
    f'<div class="stats">'
    f'<div class="stat"><div class="num mono">{len(games):,}</div><div class="what">games on sale</div></div>'
    f'<div class="stat"><div class="num mono accent">{int(games["at_historical_low"].sum()) if len(games) else 0:,}</div>'
    f'<div class="what">at their lowest price ever</div></div>'
    f'<div class="stat"><div class="num mono">{len(hits):,}</div><div class="what">watchlist matches</div></div>'
    f'</div>')
html_block(f'<div class="hero">{spotlight}{stats}</div>')

# --- Watchlist matches strip --------------------------------------------------

if not hits.empty:
    cards = "".join(
        deal_card(r, extra=f'<div class="target">{money(r["target_price"] - r["sale_price"])} under your target</div>')
        for _, r in hits.iterrows())
    html_block(f'<div class="section-title"><h3>On your watchlist</h3>'
               f'<span>{len(hits)} at or below target</span></div><div class="strip">{cards}</div>')

tab_deals, tab_lows, tab_history, tab_stores, tab_watch = st.tabs(
    ["Deals", "Lowest ever", "Price history", "Stores", "Watchlist"])

# --- Deals -------------------------------------------------------------------

with tab_deals:
    c1, c2, c3 = st.columns([2.2, 2, 1.3])
    search = c1.text_input("Search", placeholder="Search titles")
    stores = c2.multiselect("Stores", sorted(deals["store_name"].unique()), placeholder="All stores")
    sort = c3.selectbox("Sort by", ["Biggest discount", "Lowest price", "Biggest saving"])
    c4, c5, c6 = st.columns([2.2, 2, 1.3], vertical_alignment="bottom")
    top_price = float(max(deals["sale_price"].max(), 1)) if len(deals) else 1.0
    max_price = c4.slider("Max price", 0.0, top_price, top_price, step=1.0, format="$%.0f")
    min_discount = c5.slider("Min discount", 0, 100, 0, step=5, format="%d%%")
    view = c6.segmented_control("View", ["Cards", "Table"], default="Cards", key="deal_view")

    filtered = deals[(deals["sale_price"] <= max_price) & (deals["discount_pct"] >= min_discount)]
    if stores:
        filtered = filtered[filtered["store_name"].isin(stores)]
    if search:
        filtered = filtered[filtered["title"].str.contains(search, case=False, regex=False)]
    shown = best_per_game(filtered)
    order = {"Biggest discount": (["discount_pct", "sale_price"], [False, True]),
             "Lowest price": (["sale_price", "discount_pct"], [True, False]),
             "Biggest saving": (["saving"], [False])}[sort]
    shown = shown.assign(saving=shown["normal_price"] - shown["sale_price"]).sort_values(order[0], ascending=order[1])

    st.caption(f"{len(shown):,} games, {len(filtered):,} deals across stores")

    if shown.empty:
        empty_state("magnifying-glass", "Nothing matches those filters", "Try widening the price or discount range.")
    elif view == "Table":
        table = filtered.assign(link=filtered["deal_id"].map(deal_url))
        st.dataframe(table[["thumb", "title", "store_name", "sale_price", "normal_price", "discount_pct",
                            "historical_low", "link"]], hide_index=True, width="stretch", height=560,
                     column_config={
                         "thumb": st.column_config.ImageColumn("", width="small"),
                         "title": st.column_config.TextColumn("Game", width="large"),
                         "store_name": "Store",
                         "sale_price": st.column_config.NumberColumn("Price", format="$%.2f"),
                         "normal_price": st.column_config.NumberColumn("Normally", format="$%.2f"),
                         "discount_pct": st.column_config.NumberColumn("Discount", format="%d%%"),
                         "historical_low": st.column_config.NumberColumn("Lowest ever", format="$%.2f"),
                         "link": st.column_config.LinkColumn("", display_text="View deal"),
                     })
    else:
        limit = st.session_state.get("deal_limit", PAGE_SIZE)
        card_grid(shown, limit)
        if len(shown) > limit:
            if st.button(f"Show {min(PAGE_SIZE, len(shown) - limit)} more", key="more_deals"):
                st.session_state["deal_limit"] = limit + PAGE_SIZE
                st.rerun()

# --- Lowest ever ----------------------------------------------------------------

with tab_lows:
    lows = games[games["at_historical_low"] == 1].sort_values("discount_pct", ascending=False)
    if lows.empty:
        empty_state("trend-down", "Nothing at its lowest price right now",
                    "Games show up here when a store matches or beats the lowest price CheapShark has recorded.")
    else:
        st.caption(f"{len(lows)} games matching or beating the lowest price CheapShark has ever recorded for them.")
        card_grid(lows)

# --- Price history ------------------------------------------------------------

with tab_history:
    search = st.text_input("Search for a game", placeholder="e.g. Baldur's Gate", key="history_search")
    if not search:
        empty_state("chart-line-up", "Look up a game",
                    "Search above to chart its price at every store across your snapshots.")
    else:
        history = queries.price_history(conn, search)
        if history.empty:
            empty_state("magnifying-glass", f"No price history for '{esc(search)}'",
                        "Only games that have appeared in a snapshot are tracked. Add it to your watchlist to start.")
        else:
            game = st.selectbox("Game", sorted(history["title"].unique()))
            game_history = history[history["title"] == game].copy()
            game_history["fetched_at"] = pd.to_datetime(game_history["fetched_at"])
            row = pd.read_sql_query(
                "SELECT thumb, steam_app_id, cheapest_ever, cheapest_ever_date FROM games WHERE title = ? LIMIT 1",
                conn, params=(game,)).iloc[0]
            latest = game_history[game_history["fetched_at"] == game_history["fetched_at"].max()]
            best_now = latest.sort_values("sale_price").iloc[0]
            low = row["cheapest_ever"]
            html_block(
                f'<div class="gamehead"><div class="art" style="{art_style(row)}"></div><div class="figs">'
                f'<div class="fig"><div class="num mono">{money(best_now["sale_price"])}</div>'
                f'<div class="what">Cheapest now, at {esc(best_now["store_name"])}</div></div>'
                + (f'<div class="fig"><div class="num mono">{money(low)}</div>'
                   f'<div class="what">Lowest ever{nice_date(row["cheapest_ever_date"])}</div></div>'
                   if pd.notna(low) else "")
                + f'<div class="fig"><div class="num mono">{game_history["fetched_at"].nunique()}</div>'
                  f'<div class="what">snapshots</div></div></div></div>')

            lines = alt.Chart(game_history).mark_line(point=alt.OverlayMarkDef(size=36), interpolate="step-after",
                                                      strokeWidth=2).encode(
                x=alt.X("fetched_at:T", title=None, axis=alt.Axis(format="%b %d, %H:%M", tickCount=6)),
                y=alt.Y("sale_price:Q", title="Price ($)", scale=alt.Scale(zero=True)),
                color=alt.Color("store_name:N", title="Store", scale=alt.Scale(range=SERIES)),
                tooltip=[alt.Tooltip("store_name", title="Store"),
                         alt.Tooltip("sale_price", title="Price", format="$.2f"),
                         alt.Tooltip("discount_pct", title="Discount %"),
                         alt.Tooltip("fetched_at:T", title="Fetched", format="%b %d %H:%M")],
            )
            chart = lines
            if pd.notna(low):
                chart = lines + alt.Chart(pd.DataFrame({"low": [low]})).mark_rule(
                    strokeDash=[5, 4], color=MUTED).encode(
                    y="low:Q", tooltip=[alt.Tooltip("low", title="Lowest ever", format="$.2f")])
            st.altair_chart(chart_style(chart.properties(height=340)), width="stretch", theme=None)
            if game_history["fetched_at"].nunique() == 1:
                st.caption("Only one snapshot so far. The chart fills in as more fetches run. "
                           "The dashed line is the lowest price ever recorded.")
            else:
                st.caption("The dashed line is the lowest price ever recorded.")

# --- Stores ---------------------------------------------------------------------

with tab_stores:
    by_store = queries.deals_by_store(conn)
    left, right = st.columns(2, gap="large")
    bars = alt.Chart(by_store).mark_bar(color=ACCENT, cornerRadiusEnd=3, height=14)
    with left:
        st.markdown("##### Deals per store")
        st.altair_chart(chart_style(bars.encode(
            x=alt.X("deal_count:Q", title="Deals"),
            y=alt.Y("store_name:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("store_name", title="Store"), alt.Tooltip("deal_count", title="Deals")],
        ).properties(height=34 * max(len(by_store), 1))), width="stretch", theme=None)
    with right:
        st.markdown("##### Average discount")
        st.altair_chart(chart_style(bars.encode(
            x=alt.X("avg_discount:Q", title="Average discount (%)", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("store_name:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("store_name", title="Store"), alt.Tooltip("avg_discount", title="Avg discount %")],
        ).properties(height=34 * max(len(by_store), 1))), width="stretch", theme=None)

# --- Watchlist --------------------------------------------------------------------

with tab_watch:
    status = queries.watchlist_status(conn)
    if status.empty:
        empty_state("target", "Your watchlist is empty",
                    "Add a game and a target price in the sidebar. You'll get an alert when it drops to that price.")
    else:
        rows = []
        for _, r in status.iterrows():
            if pd.isna(r["sale_price"]):
                detail = '<div class="sub">Not in the latest snapshot. It will be looked up on the next fetch.</div>'
                verdict = '<span class="off">Not seen yet</span>'
                art = '<div class="art"></div>'
            else:
                others = int(r["matching_games"]) - 1
                more = f", plus {others} other match{'es' if others != 1 else ''}" if others > 0 else ""
                detail = (f'<div class="sub"><a href="{deal_url(r["deal_id"])}" target="_blank" rel="noopener">'
                          f'{esc(r["title"])}</a> at {esc(r["store_name"])}{more}</div>')
                diff = r["target_price"] - r["sale_price"]
                verdict = (f'<span class="good mono">{money(r["sale_price"])}</span>'
                           f'<div class="sub">{money(diff)} under target</div>' if diff >= 0 else
                           f'<span class="off mono">{money(r["sale_price"])}</span>'
                           f'<div class="sub">{money(-diff)} above target</div>')
                art = f'<div class="art" style="{art_style(r)}"></div>'
            rows.append(f'<div class="watchrow">{art}<div><div class="q">{esc(r["title_query"])}</div>'
                        f'<div class="sub">Alert at or below {money(r["target_price"])}</div>{detail}</div>'
                        f'<div class="status">{verdict}</div></div>')
        html_block("".join(rows))
