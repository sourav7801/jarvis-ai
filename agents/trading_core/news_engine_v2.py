
from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any


FEEDS = {
    "nifty": "https://news.google.com/rss/search?q=Nifty+50+India+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "banknifty": "https://news.google.com/rss/search?q=BankNifty+India+banking+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "sensex": "https://news.google.com/rss/search?q=Sensex+BSE+India+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "crude": "https://news.google.com/rss/search?q=crude+oil+India+Hormuz+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "macro": "https://news.google.com/rss/search?q=India+RBI+Fed+inflation+markets+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "gold": "https://news.google.com/rss/search?q=gold+silver+India+markets+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
}


def clean(x: str) -> str:
    x = html.unescape(x or "")
    return re.sub(r"\s+", " ", x).strip()


def parse_pub_date(raw: str):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        return None


def classify(title: str) -> dict[str, Any]:
    t = title.lower()
    markets = set()
    sectors = set()

    if any(x in t for x in ["nifty", "india", "nse"]):
        markets.add("NIFTY")
    if any(x in t for x in ["sensex", "bse"]):
        markets.add("SENSEX")
    if any(x in t for x in ["bank nifty", "banknifty", "banking", "banks", "hdfc bank", "icici", "sbi"]):
        markets.add("BANKNIFTY")
        sectors.add("BANKING")
    if any(x in t for x in ["crude", "oil", "opec", "hormuz"]):
        markets.add("CRUDE_OIL")
        sectors.add("ENERGY")
    if any(x in t for x in ["gold", "silver"]):
        markets.add("GOLD")
    if any(x in t for x in ["rbi", "repo", "inflation", "cpi", "fed", "fomc", "rate decision", "tariff", "war", "geopolitical"]):
        impact = "HIGH"
    else:
        impact = "MEDIUM" if markets else "LOW"

    positive = ["surge", "rises", "gain", "record high", "bullish", "relief", "inflows", "growth"]
    negative = ["fall", "falls", "drop", "drops", "crash", "weak", "risk", "war", "oil shock", "uncertainty"]

    if any(x in t for x in positive):
        direction = "POSITIVE"
    elif any(x in t for x in negative):
        direction = "NEGATIVE"
    else:
        direction = "NEUTRAL"

    return {
        "markets": sorted(markets),
        "sectors": sorted(sectors),
        "impact": impact,
        "direction": direction,
    }


class NewsEngineV2:
    def __init__(self, freshness_hours: int = 36):
        self.freshness = timedelta(hours=freshness_hours)

    def fetch(self, limit_per_feed: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        items = []

        for source, url in FEEDS.items():
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "JARVIS-Trading-Agent/2.0"},
                )
                raw = urllib.request.urlopen(req, timeout=10).read()
                root = ET.fromstring(raw)

                for item in root.findall(".//item")[:limit_per_feed]:
                    title = clean(item.findtext("title", ""))
                    link = clean(item.findtext("link", ""))
                    pub_raw = clean(item.findtext("pubDate", ""))
                    pub_dt = parse_pub_date(pub_raw)

                    # Reject stale/misdated feed items.
                    if pub_dt is None:
                        continue
                    if now - pub_dt > self.freshness:
                        continue
                    if pub_dt - now > timedelta(hours=2):
                        continue

                    c = classify(title)

                    items.append({
                        "source": source,
                        "title": title,
                        "url": link,
                        "published": pub_dt.isoformat(),
                        **c,
                    })
            except Exception:
                continue

        # Deduplicate by normalized title.
        seen = set()
        out = []

        for x in items:
            key = re.sub(
                r"[^a-z0-9]+",
                " ",
                x["title"].lower(),
            ).strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(x)

        rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        out.sort(
            key=lambda x: (
                rank.get(x["impact"], 0),
                x["published"],
            ),
            reverse=True,
        )
        return out[:50]
