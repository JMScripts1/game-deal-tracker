# Sends watchlist alerts to the terminal and, if configured, a Discord channel

import os

import requests

EMBEDS_PER_MESSAGE = 10  # Discord's limit
GREEN = 0x2ECC71
GOLD = 0xF1C40F


def webhook_url():
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None


def deal_url(deal_id):
    # deal ids from CheapShark are already URL-encoded
    return f"https://www.cheapshark.com/redirect?dealID={deal_id}"


def format_alert(alert):
    line = (f"{alert['title']}: ${alert['sale_price']:.2f} at {alert['store_name']} "
            f"(target ${alert['target_price']:.2f}, normally ${alert['normal_price']:.2f})")
    if alert["at_historical_low"]:
        line += " - historical low!"
    return line


def _embed(alert):
    description = (f"**${alert['sale_price']:.2f}** at {alert['store_name']}\n"
                   f"Normally ${alert['normal_price']:.2f} ({alert['discount_pct']:.0f}% off)\n"
                   f"Your target: ${alert['target_price']:.2f}")
    if alert["at_historical_low"]:
        description += "\n**Historical low price**"
    embed = {
        "title": alert["title"],
        "url": deal_url(alert["deal_id"]),
        "description": description,
        "color": GOLD if alert["at_historical_low"] else GREEN,
        "footer": {"text": f"Watching \"{alert['watching']}\""},
    }
    if alert.get("thumb"):
        embed["thumbnail"] = {"url": alert["thumb"]}
    return embed


def send_discord(alerts, url):
    embeds = [_embed(a) for a in alerts]
    for i in range(0, len(embeds), EMBEDS_PER_MESSAGE):
        payload = {"username": "Game Deal Tracker", "embeds": embeds[i:i + EMBEDS_PER_MESSAGE]}
        if i == 0:
            payload["content"] = f"{len(alerts)} watched game{'s' if len(alerts) != 1 else ''} hit your target price"
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()


def send_test(url):
    response = requests.post(url, json={
        "username": "Game Deal Tracker",
        "content": "Test message: your Discord alerts are set up correctly.",
    }, timeout=15)
    response.raise_for_status()


def notify(alerts):
    """Print alerts and send them to Discord. Returns False if Discord delivery failed."""
    print("=== Watchlist alerts ===")
    for alert in alerts:
        print(format_alert(alert))

    url = webhook_url()
    if not url:
        return True
    try:
        send_discord(alerts, url)
    except requests.RequestException as e:
        print(f"Could not send Discord alert: {e}")
        return False
    print(f"Sent {len(alerts)} alert{'s' if len(alerts) != 1 else ''} to Discord.")
    return True
