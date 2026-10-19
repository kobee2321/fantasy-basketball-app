"""Generate clearly-labelled DEMO leagues (synthetic stats) so the site works before Yahoo is connected."""
import os
import random

from common import MY_TEAM, load

HERE = os.path.dirname(os.path.abspath(__file__))
CATS = ["PTS", "REB", "AST", "STL", "BLK", "3PTM", "FG%", "FT%", "TO"]
POS = ["PG", "SG", "SF", "PF", "C"]
TEAM_NAMES = [
    ["Beach Boys", "Hoop Dreams", "Splash Bros", "Dunk Dynasty", "Court Jesters", "Fast Break Club",
     "Triple Doubles", "Paint Patrol", "Glass Cleaners", "Buzzer Beaters"],
    ["Midnight Hoopers", "Net Ninjas", "Rim Rockers", "Tall Tales", "Pick & Roll Pals", "Zone Defense",
     "Hardwood Heroes", "Bounce Back", "Alley-Oop Army", "Clutch Gene"],
    ["Rebound Kings", "Dribble Drive", "Swish Squad", "The Closers", "Crossover Crew", "Full Court Press",
     "Bank Shot", "Lob City 2", "Sixth Men", "Iso Joes"],
]


def _player(name, rank, rng, pos):
    v = max(0.02, 1 - rank / 330)
    prof = {c: rng.uniform(0.6, 1.4) for c in CATS}
    season = {
        "PTS": 4 + 24 * v ** 1.2 * prof["PTS"], "REB": 1.5 + 9 * v ** 1.1 * prof["REB"],
        "AST": 0.8 + 8 * v ** 1.2 * prof["AST"], "STL": 0.3 + 1.6 * v * prof["STL"] / 1.2,
        "BLK": 0.1 + 1.6 * v * prof["BLK"] / 1.2, "3PTM": 0.3 + 3.4 * v * prof["3PTM"] / 1.2,
        "FG%": min(0.62, 0.40 + 0.08 * v + 0.03 * prof["FG%"]), "FT%": min(0.92, 0.65 + 0.12 * v + 0.05 * prof["FT%"]),
        "TO": 0.8 + 3.0 * v * prof["TO"] / 1.2,
    }
    season = {k: round(x, 3 if "%" in k else 1) for k, x in season.items()}
    recent = {k: round(x * (1 + rng.uniform(-0.12, 0.12)) if "%" not in k else
                       min(0.95, x * (1 + rng.uniform(-0.04, 0.04))), 3 if "%" in k else 1)
              for k, x in season.items()}
    status = "INJ" if rng.random() < 0.03 else ""
    return {"id": f"demo.p.{abs(hash(name)) % 10**6}", "name": name, "pos": pos, "team": "", "status": status,
            "injury": "", "season": season, "recent": recent}


def make(seed=7):
    ranks = load(os.path.join(HERE, "demo_ranks.json"))
    rng = random.Random(seed)
    leagues = []
    for li, names in enumerate(TEAM_NAMES):
        pool = [(n, r) for n, r, _ in ranks if r <= 300]
        pool.sort(key=lambda x: x[1] + rng.uniform(-8, 8))
        pool = [(n, r, POS[i % 5] + ("," + POS[(i + 1) % 5] if i % 3 == 0 else "")) for i, (n, r) in enumerate(pool)]
        team_names = names[:9] + [MY_TEAM]
        rng.shuffle(team_names)
        teams = [{"key": f"demo.l.{li}.t.{i}", "name": nm, "mine": nm == MY_TEAM, "rank": None, "record": "0-0-0",
                  "players": []} for i, nm in enumerate(team_names)]
        k = 0
        for rnd in range(13):                       # snake draft
            order = range(10) if rnd % 2 == 0 else range(9, -1, -1)
            for ti in order:
                n, r, pos = pool[k]
                teams[ti]["players"].append(_player(n, r, rng, pos))
                k += 1
        fa = [_player(n, r, rng, pos) for n, r, pos in pool[k:k + 90]]
        leagues.append({"league_key": f"demo.l.{li}", "name": f"DEMO League {li + 1}", "season": "2026",
                        "points": False, "demo": True,
                        "categories": [{"id": str(i), "name": c, "lower_better": c == "TO", "pct": c.endswith("%")}
                                       for i, c in enumerate(CATS)],
                        "teams": teams, "free_agents": fa})
    return leagues
