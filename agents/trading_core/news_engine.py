
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


FEEDS = {
    "google_nifty": "https://news.google.com/rss/search?q=Nifty+50+India+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "google_banknifty": "https://news.google.com/rss/search?q=BankNifty+India+banking+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "google_sensex": "https://news.google.com/rss/search?q=Sensex+BSE+India+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "google_crude": "https://news.google.com/rss/search?q=crude+oil+India+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "google_gold": "https://news.google.com/rss/search?q=gold+India+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "google_macro": "https://news.google.com/rss/search?q=India+RBI+Fed+inflation+markets+when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
}


def clean(text: str) -> str:
    text = html.unescape(text or "")
    return re.sub(r"\s+", " ", text).strip()


def classify(title: str) -> dict[str, Any]:
    t = title.lower()
    markets = []
    sectors = []
    impact = "LOW"
    direction = "NEUTRAL"

    if any(x in t for x in ["rbi", "repo", "inflation", "cpi", "fed", "fomc", "rate", "war", "tariff", "crude"]):
        impact = "HIGH"

    if any(x in t for x in ["bank", "hdfc", "icici", "sbi", "financial"]):
        markets.append("BANKNIFTY")
        sectors.append("BANKING")

    if any(x in t for x in ["nifty", "sensex", "india", "nse", "bse"]):
        markets.extend(["NIFTY", "SENSEX"])

    if any(x in t for x in ["oil", "crude", "opec"]):
        markets.extend(["NIFTY", "CRUDE_OIL"])
        sectors.append("ENERGY")

    if any(x in t for x in ["it", "infosys", "tcs", "wipro"]):
        sectors.append("IT")

    if any(x in t for x in ["surge", "rises", "gain", "bullish", "upbeat", "record high"]):
        direction = "POSITIVE"
        impact = "MEDIUM" if impact == "LOW" else impact
    elif any(x in t for x in ["fall", "drops", "cuts", "bearish", "crisis", "weak"]):
        direction = "NEGATIVE"
        impact = "MEDIUM" if impact == "LOW" else impact

    return {
        "markets": sorted(set(markets)),
        "sectors": sorted(set(sectors)),
        "impact": impact,
        "direction": direction,
    }


class NewsEngine:
    def fetch(self, limit_per_feed: int = 8) -> list[dict[str, Any]]:
        items = []

        for source, url in FEEDS.items():
            try:
                raw = urllib.request.urlopen(
                    urllib.request.Request(
                        url,
                        headers={"User-Agent": "JARVIS-Trading-Agent/1.0"},
                    ),
                    timeout=10,
                ).read()

                root = ET.fromstring(raw)
                for item in root.findall(".//item")[:limit_per_feed]:
                    title = clean(item.findtext("title", ""))
                    link = clean(item.findtext("link", ""))
                    published = clean(item.findtext("pubDate", ""))
                    c = classify(title)

                    items.append(
                        {
                            "source": source,
                            "title": title,
                            "url": link,
                            "published": published,
                            **c,
                        }
                    )
            except Exception:
                continue

        # Deduplicate and rank.
        seen = set()
        out = []
        for x in items:
            key = x["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(x)

        rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        out.sort(
            key=lambda x: (
                rank.get(x["impact"], 0),
                len(x["markets"]),
                x["published"],
            ),
            reverse=True,
        )
        return out[:50]
