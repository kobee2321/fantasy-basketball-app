"""Yahoo Fantasy Sports API client (OAuth2 refresh-token flow) -> normalised league data.

Environment variables (GitHub Actions secrets):
    YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_REFRESH_TOKEN

Run `python scripts/yahoo_api.py --probe` locally (with the same variables set) to print the
raw responses if Yahoo ever changes its format.

NOTE: written against Yahoo's documented v2 endpoints and tested on a fixture of the response
shape (tests/test_parsers.py), but not against a live account.
"""
import base64
import os
import sys
import time

import requests

from common import MY_TEAM, norm, num

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
_tok = {"value": None, "exp": 0}


def configured():
    return all(os.environ.get(k) for k in ("YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET", "YAHOO_REFRESH_TOKEN"))


def access_token():
    if _tok["value"] and time.time() < _tok["exp"] - 60:
        return _tok["value"]
    cid, sec = os.environ["YAHOO_CLIENT_ID"], os.environ["YAHOO_CLIENT_SECRET"]
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": os.environ["YAHOO_REFRESH_TOKEN"],
              "redirect_uri": "oob"},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    _tok.update(value=j["access_token"], exp=time.time() + int(j.get("expires_in", 3600)))
    return _tok["value"]


def get(path):
    sep = "&" if "?" in path else "?"
    for attempt in range(3):
        r = requests.get(BASE + path + sep + "format=json",
                         headers={"Authorization": f"Bearer {access_token()}"}, timeout=45)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


# ---------- Yahoo JSON helpers (their JSON is XML-shaped: lists of single-key dicts) ----------
def flat(x):
    """Merge a list of dicts / nested lists into one dict."""
    if isinstance(x, dict):
        return x
    d = {}
    if isinstance(x, list):
        for i in x:
            d.update(flat(i))
    return d


def coll(c, key):
    """Items of a Yahoo collection {'0': {key: ...}, '1': {...}, 'count': n}."""
    if not isinstance(c, dict):
        return []
    return [c[str(i)][key] for i in range(int(c.get("count", 0))) if str(i) in c]


def parse_categories(settings):
    cats = []
    for s in settings.get("stat_categories", {}).get("stats", []):
        st = s["stat"]
        if str(st.get("enabled", "1")) == "0" or st.get("position_type") == "BN":
            continue
        name = st.get("display_name") or st.get("name")
        cats.append({"id": str(st["stat_id"]), "name": name,
                     "lower_better": str(st.get("sort_order", "1")) == "0",
                     "pct": name.endswith("%")})
    return cats


def parse_player(item, cats):
    """One element of a 'players' collection -> normalised player dict."""
    p = item["player"] if isinstance(item, dict) and "player" in item else item
    info = flat(p[0]) if isinstance(p, list) else flat(p)
    extra = flat(p[1:]) if isinstance(p, list) else {}
    ids = {c["id"]: c["name"] for c in cats}
    stats = {}
    for s in extra.get("player_stats", {}).get("stats", []):
        st = s["stat"]
        nm = ids.get(str(st["stat_id"]))
        if nm:
            stats[nm] = num(st.get("value"))
    nm = info.get("name", {})
    return {
        "id": str(info.get("player_key") or info.get("player_id")),
        "name": nm.get("full") if isinstance(nm, dict) else str(nm),
        "pos": info.get("display_position", ""),
        "team": info.get("editorial_team_abbr", ""),
        "status": info.get("status", ""),
        "injury": info.get("injury_note", ""),
        "_stats": stats,
    }


def find_teams(node):
    if isinstance(node, dict):
        if "teams" in node and isinstance(node["teams"], dict) and "count" in node["teams"]:
            return node["teams"]
        for v in node.values():
            r = find_teams(v)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_teams(v)
            if r is not None:
                return r
    return None


def find_players(node):
    """Recursively locate the Yahoo 'players' collection inside any response."""
    if isinstance(node, dict):
        if "players" in node and isinstance(node["players"], dict) and "count" in node["players"]:
            return node["players"]
        for v in node.values():
            r = find_players(v)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_players(v)
            if r is not None:
                return r
    return None


def parse_players(j, cats):
    c = find_players(j) or {}
    return [parse_player(c[str(i)], cats) for i in range(int(c.get("count", 0))) if str(i) in c]


def _fetch_players(path_tpl, cats, stat_type):
    """Try a few URL spellings; return list of players with stats of `stat_type`."""
    last = None
    for tpl in path_tpl:
        try:
            return parse_players(get(tpl.format(t=stat_type)), cats)
        except requests.HTTPError as e:
            last = e
    raise last or RuntimeError("no player endpoint worked")


def fetch_all(season=None):
    """Return normalised data for every NBA league of the logged-in user."""
    j = get("/users;use_login=1/games;game_codes=nba/leagues")
    user = coll(j["fantasy_content"]["users"], "user")[0]
    games = coll(flat(user[1:])["games"], "game")
    games = [flat(g) for g in games]
    seasons = sorted({g.get("season") for g in games if g.get("season")})
    season = str(season or seasons[-1])
    leagues = []
    for g in games:
        if str(g.get("season")) != season:
            continue
        for lg in coll(g.get("leagues", {}), "league"):
            lg = flat(lg)
            leagues.append(_fetch_league(lg, season))
    return leagues


def _fetch_league(lg, season):
    lk = lg["league_key"]
    jset = get(f"/league/{lk}/settings")
    L = jset["fantasy_content"]["league"]
    settings = flat(flat(L[1:])["settings"])
    cats = parse_categories(settings)
    points = settings.get("scoring_type", lg.get("scoring_type", "head")) in ("headpoint", "point")
    weights = {}
    if points:
        for m in settings.get("stat_modifiers", {}).get("stats", []):
            st = m["stat"]
            weights[str(st["stat_id"])] = num(st.get("value"))
    jst = get(f"/league/{lk}/standings")
    teams_raw = coll(find_teams(jst), "team")
    teams = []
    for t in teams_raw:
        t = flat(t)
        ot = t.get("team_standings", {}).get("outcome_totals", {})
        team = {"key": t["team_key"], "name": t["name"],
                "mine": str(t.get("is_owned_by_current_login", "0")) == "1" or norm(t["name"]) == norm(MY_TEAM),
                "rank": int(num(t.get("team_standings", {}).get("rank"), 0)) or None,
                "record": f"{ot.get('wins', 0)}-{ot.get('losses', 0)}-{ot.get('ties', 0)}"}
        team["players"] = _merge(
            _fetch_players(["/team/" + t["team_key"] + "/roster/players/stats;type={t}"], cats, "average_season"),
            _fetch_players(["/team/" + t["team_key"] + "/roster/players/stats;type={t}"], cats, "lastmonth"),
        )
        teams.append(team)
    fa = []
    for status in ("FA", "W"):
        for start in range(0, 100, 25):
            base = f"/league/{lk}/players;status={status};sort=AR;count=25;start={start}/stats;type=" + "{t}"
            try:
                a = _fetch_players([base], cats, "average_season")
                b = _fetch_players([base], cats, "lastmonth")
            except Exception:  # noqa: BLE001 - keep going with what we have
                break
            if not a:
                break
            fa += _merge(a, b)
    league = {"league_key": lk, "name": lg.get("name", lk), "season": season, "points": points,
              "categories": cats, "teams": teams, "free_agents": fa}
    if points:
        league["categories"] = [{"id": "fpts", "name": "FPTS", "lower_better": False, "pct": False}]
        id_by_name = {c["name"]: c["id"] for c in cats}
        for p in [p for t in teams for p in t["players"]] + fa:
            for key in ("season", "recent"):
                p[key] = {"FPTS": round(sum(weights.get(id_by_name.get(n), 0) * v
                                           for n, v in p.get(key, {}).items()), 2)}
    return league


def _merge(season_list, recent_list):
    rec = {p["id"]: p["_stats"] for p in recent_list}
    out = []
    for p in season_list:
        q = {k: v for k, v in p.items() if k != "_stats"}
        q["season"] = p["_stats"]
        q["recent"] = rec.get(p["id"]) or p["_stats"]
        out.append(q)
    return out


if __name__ == "__main__":
    if "--probe" in sys.argv:
        import json
        print(json.dumps(get("/users;use_login=1/games;game_codes=nba/leagues"), indent=1)[:6000])
    else:
        import json
        print(json.dumps(fetch_all(), indent=1)[:4000])
