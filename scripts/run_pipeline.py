"""Daily pipeline: fetch leagues -> read articles -> analyse -> write data/latest.json.

Usage: python scripts/run_pipeline.py [--demo]
Data source priority: Yahoo API (if secrets set) > data/import/leagues.json (manual) > demo data.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import analysis
import articles
import yahoo_api
from common import DATA, IMPORT_DIR, load, save

HKT = timezone(timedelta(hours=8))


def get_leagues(force_demo=False):
    if not force_demo and yahoo_api.configured():
        try:
            return yahoo_api.fetch_all(), "yahoo"
        except Exception as e:  # noqa: BLE001
            print("Yahoo fetch failed:", repr(e), file=sys.stderr)
            if not load(os.path.join(IMPORT_DIR, "leagues.json")):
                raise
    manual = None if force_demo else load(os.path.join(IMPORT_DIR, "leagues.json"))
    if manual:
        return manual, "manual"
    from make_demo import make
    return make(), "demo"


def main():
    leagues, source = get_leagues("--demo" in sys.argv)
    names = [p["name"] for lg in leagues for t in lg["teams"] for p in t["players"]] + \
            [p["name"] for lg in leagues for p in lg["free_agents"]]
    buzz, errors = articles.run(names)
    result = analysis.analyse_all(leagues, buzz)
    now = datetime.now(timezone.utc)
    save(os.path.join(DATA, "latest.json"), {
        "generated": now.isoformat(),
        "generated_hkt": now.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT"),
        "source": source, "demo": source == "demo", "feed_errors": errors, "leagues": result})
    print(f"source={source} leagues={len(result)} feed_errors={len(errors)}")


if __name__ == "__main__":
    main()
