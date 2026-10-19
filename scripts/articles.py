"""Read NBA expert articles / player-news RSS feeds (last 3 days) and score player 'buzz'."""
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from common import DATA, IMPORT_DIR, load, norm, save
import os

DEFAULT_FEEDS = [
    {"name": "RotoWire", "url": "https://www.rotowire.com/rss/news.php?sport=NBA", "weight": 1.3},
    {"name": "Yahoo Sports", "url": "https://sports.yahoo.com/nba/rss.xml", "weight": 1.2},
    {"name": "ESPN", "url": "https://www.espn.com/espn/rss/nba/news", "weight": 1.0},
    {"name": "CBS Sports", "url": "https://www.cbssports.com/rss/headlines/nba/", "weight": 1.0},
    {"name": "NBA.com", "url": "https://www.nba.com/rss/nba_rss.xml", "weight": 0.8},
]
POS_WORDS = ["waiver", "pick up", "pickup", "add ", "stash", "breakout", "starting", "starter", "expanded role",
             "more minutes", "surge", "career-high", "career high", "triple-double", "returns", "back in",
             "extension", "sleeper", "hot", "trending up", "must-add", "streaming"]
NEG_WORDS = ["out for", "ruled out", "sidelined", "injury", "injured", "surgery", "benched", "suspended",
             "minutes restriction", "doubtful", "drop", "trending down", "fall", "miss"]
WINDOW_DAYS = 3
UA = {"User-Agent": "Mozilla/5.0 (fantasy-basketball-app)"}


def _parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def parse_feed(xml_text, source, weight=1.0):
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        g = {c.tag.split("}")[-1]: c for c in it}
        link = (g["link"].text or g["link"].get("href")) if "link" in g else ""
        dnode = next((g[k] for k in ("pubDate", "published", "updated", "date") if k in g), None)
        date = _parse_date(dnode.text if dnode is not None else None)
        body = _strip((g["description"].text if "description" in g else "") or
                      (g["summary"].text if "summary" in g else "") or
                      (g["content"].text if "content" in g else ""))
        out.append({"source": source, "weight": weight, "title": _strip(g["title"].text) if "title" in g else "",
                    "link": (link or "").strip(), "date": date, "text": body})
    return out


def fetch_articles(feeds=None, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    feeds = feeds or (load(os.path.join(IMPORT_DIR, "feeds.json")) or DEFAULT_FEEDS)
    items, errors = [], []
    for f in feeds:
        try:
            r = requests.get(f["url"], headers=UA, timeout=25)
            r.raise_for_status()
            items += parse_feed(r.text, f["name"], f.get("weight", 1.0))
        except Exception as e:  # noqa: BLE001 - a dead feed must never break the daily run
            errors.append(f"{f['name']}: {e}")
    items = [i for i in items if i["date"] is None or i["date"] >= cutoff]
    return items, errors


def score_buzz(items, player_names):
    """{normalised name: {score, mentions, pos, neg, links}}"""
    buzz = {}
    patterns = {nm: re.compile(r"\b" + re.escape(nm) + r"\b") for nm in {norm(n) for n in player_names} if len(nm) > 5}
    for it in items:
        text = norm(it["title"] + " . " + it["text"])
        low = (it["title"] + " " + it["text"]).lower()
        pos = sum(1 for w in POS_WORDS if w in low)
        neg = sum(1 for w in NEG_WORDS if w in low)
        for nm, pat in patterns.items():
            if pat.search(text):
                b = buzz.setdefault(nm, {"score": 0.0, "mentions": 0, "pos": 0, "neg": 0, "links": []})
                b["mentions"] += 1
                b["pos"] += pos
                b["neg"] += neg
                b["score"] += it["weight"] * (0.6 + 0.5 * pos - 0.4 * neg)
                if it["link"] and len(b["links"]) < 3:
                    b["links"].append({"title": it["title"][:120], "url": it["link"], "source": it["source"]})
    for b in buzz.values():
        b["score"] = max(0.0, round(b["score"], 2))
    return buzz


def run(player_names):
    items, errors = fetch_articles()
    buzz = score_buzz(items, player_names)
    brief = sorted(({"source": i["source"], "title": i["title"], "link": i["link"],
                     "date": i["date"].isoformat() if i["date"] else None} for i in items),
                   key=lambda x: x["date"] or "", reverse=True)[:40]
    save(os.path.join(DATA, "articles.json"), {"generated": datetime.now(timezone.utc).isoformat(),
                                               "window_days": WINDOW_DAYS, "count": len(items),
                                               "errors": errors, "articles": brief})
    return buzz, errors


if __name__ == "__main__":
    b, e = run(sys.argv[1:])
    print(len(b), "players with buzz;", len(e), "feed errors")
