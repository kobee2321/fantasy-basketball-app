"""Offline tests: Yahoo response shape + RSS parsing. Run: python tests/test_parsers.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import yahoo_api as y, articles as a
from datetime import datetime, timezone

cats = [{"id": "5", "name": "FG%", "lower_better": False, "pct": True},
        {"id": "12", "name": "PTS", "lower_better": False, "pct": False},
        {"id": "19", "name": "TO", "lower_better": True, "pct": False}]
player = lambda key, name, st, status="": {"player": [[{"player_key": key}, {"player_id": key.split('.')[-1]},
    {"name": {"full": name}}, {"editorial_team_abbr": "Den"}, {"display_position": "C"}, {"status": status}],
    {"player_stats": {"coverage_type": "season", "stats": [{"stat": {"stat_id": "5", "value": ".583"}},
     {"stat": {"stat_id": "12", "value": st}}, {"stat": {"stat_id": "19", "value": "-"}}]}}]}
roster = {"fantasy_content": {"team": [[{"team_key": "428.l.1.t.1"}, {"name": "X"}],
          {"roster": {"coverage_type": "date", "0": {"players": {"0": player("428.p.1", "Nikola Jokić", "26.4", "INJ"),
                                                                   "1": player("428.p.2", "Test Guy", "10"), "count": 2}}}}]}}
ps = y.parse_players(roster, cats)
assert [p["name"] for p in ps] == ["Nikola Jokić", "Test Guy"], ps
assert ps[0]["_stats"] == {"FG%": 0.583, "PTS": 26.4, "TO": 0.0} and ps[0]["status"] == "INJ"
fa = {"fantasy_content": {"league": [{"league_key": "428.l.1"}, {"players": {"0": player("428.p.3", "FA One", "5"), "count": 1}}]}}
assert y.parse_players(fa, cats)[0]["id"] == "428.p.3"
merged = y._merge(ps, ps)
assert merged[0]["season"]["PTS"] == 26.4 and merged[0]["recent"]["PTS"] == 26.4 and "_stats" not in merged[0]
settings = {"stat_categories": {"stats": [{"stat": {"stat_id": 5, "display_name": "FG%", "sort_order": "1", "enabled": "1"}},
            {"stat": {"stat_id": 19, "display_name": "TO", "sort_order": "0", "enabled": "1"}}]}}
pc = y.parse_categories(settings)
assert pc[0]["pct"] and pc[1]["lower_better"]

now = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
rss = """<rss><channel><item><title>Reed Sheppard a must-add pickup after starting role</title><link>http://x/1</link>
<pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate><description>&lt;p&gt;Reed Sheppard posted a career-high.&lt;/p&gt;</description></item>
<item><title>Old news Reed Sheppard</title><link>http://x/2</link><pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Jimmy Butler ruled out for surgery</title><link>http://x/3</link><pubDate>Tue, 20 Oct 2026 01:00:00 GMT</pubDate></item></channel></rss>"""
items = a.parse_feed(rss, "Test", 1.0)
assert len(items) == 3
recent = [i for i in items if i["date"] >= now.replace(day=17)]
assert len(recent) == 2
b = a.score_buzz(recent, ["Reed Sheppard", "Jimmy Butler"])
assert b["reed sheppard"]["mentions"] == 1 and b["reed sheppard"]["score"] > b["jimmy butler"]["score"]
atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link href="http://z"/><updated>2026-10-19T10:00:00Z</updated><summary>s</summary></entry></feed>'
assert a.parse_feed(atom, "A")[0]["link"] == "http://z"
print("all parser tests passed")
