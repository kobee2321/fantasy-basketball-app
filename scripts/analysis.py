"""Rule-based, bilingual (EN / 繁體中文) fantasy analysis. No external AI service involved.

Input : normalised leagues (see yahoo_api.py) + article buzz {normalised name: {...}}
Output: per league -> projected ranking, per-team analysis, waiver top 10, trade suggestions.
"""
import math
import statistics as st

from common import MY_TEAM, cat_label, cat_list, norm

CORE = 10          # roster spots that count toward a team's weekly totals
BIGS = ("C", "PF")


# ------------------------------------------------------------------ player values
def _zstats(pool, cats):
    out = {}
    for c in cats:
        vals = [p["season"].get(c["name"], 0.0) for p in pool if any(p["season"].values())]
        m = st.mean(vals) if vals else 0.0
        s = st.pstdev(vals) if len(vals) > 1 else 1.0
        out[c["name"]] = (m, s or 1.0)
    return out


def _z(p, c, zs, key="season"):
    m, s = zs[c["name"]]
    v = p.get(key, {}).get(c["name"], 0.0)
    z = (v - m) / s
    return -z if c["lower_better"] else z


def player_value(p, cats, zs, key="season"):
    return sum(_z(p, c, zs, key) for c in cats)


def _active(p):
    return p.get("status") not in ("INJ", "O", "NA") and any(p["season"].values())


# ------------------------------------------------------------------ team totals
def team_totals(players, cats, zs):
    core = sorted((p for p in players if _active(p)), key=lambda p: -p["_v"])[:CORE]
    tot = {}
    for c in cats:
        vals = [p["season"].get(c["name"], 0.0) for p in core]
        tot[c["name"]] = (sum(vals) / len(vals) if c["pct"] else sum(vals)) if vals else 0.0
    return tot


def _team_scores(totals_by_team, cats):
    """z-score of every team in every category + overall score."""
    scores = {t: {} for t in totals_by_team}
    for c in cats:
        vals = [totals_by_team[t][c["name"]] for t in totals_by_team]
        m, s = st.mean(vals), (st.pstdev(vals) or 1.0)
        for t in totals_by_team:
            z = (totals_by_team[t][c["name"]] - m) / s
            scores[t][c["name"]] = -z if c["lower_better"] else z
    return scores


# ------------------------------------------------------------------ text helpers
def _t(en, zh):
    return {"en": en, "zh": zh}


def _fmt(v, c):
    return f"{v:.3f}" if c["pct"] else f"{v:.1f}"


# ------------------------------------------------------------------ suggestions
def fa_picks(team, pool_fa, cats, zs, tz, n, buzz, weights_from=None):
    """Free-agent / waiver suggestions for `team` weighted toward its weak categories."""
    tzs = weights_from or tz
    w = {c["name"]: max(0.4, 1.0 + 0.6 * max(0.0, -tzs[c["name"]]) - 0.3 * max(0.0, tzs[c["name"]] - 1.0))
         for c in cats}
    roster = sorted(team["players"], key=lambda p: p["_v"])
    droppable = [p for p in roster if p.get("status") not in ("INJ", "O", "NA")]
    cands = []
    for p in pool_fa:
        if not any(p["season"].values()) and not any(p["recent"].values()):
            continue
        if p.get("status") in ("INJ", "O", "NA"):
            continue
        parts = {}
        for c in cats:
            zs_season = _z(p, c, zs, "season")
            zs_recent = _z(p, c, zs, "recent")
            parts[c["name"]] = (0.4 * zs_season + 0.6 * zs_recent) * w[c["name"]]
        base = sum(parts.values())
        b = buzz.get(norm(p["name"]), {})
        bscore = min(3.0, b.get("score", 0.0))
        cands.append((base + 0.9 * bscore, p, parts, b, bscore))
    cands.sort(key=lambda x: -x[0])
    out = []
    for score, p, parts, b, bscore in cands[:n]:
        top = sorted(parts, key=lambda k: -parts[k])[:2]
        weak_top = [k for k in top if tz[k] < 0.3] or top
        drop = droppable[0] if droppable else None
        rec_vals = ", ".join(f"{cat_label(c['name'], 'en')} {_fmt(p['recent'].get(c['name'], 0), c)}"
                             for c in cats[:4])
        en = (f"Helps {cat_list(weak_top, 'en')}. Last-30-day: {rec_vals}.")
        zh = (f"補強{cat_list(weak_top, 'zh')}。近30天：" +
              "，".join(f"{cat_label(c['name'], 'zh')} {_fmt(p['recent'].get(c['name'], 0), c)}" for c in cats[:4]) + "。")
        if b.get("mentions"):
            en += f" Mentioned in {b['mentions']} expert article(s) in the last 3 days" + (
                " (positive buzz)." if b.get("pos", 0) > b.get("neg", 0) else ".")
            zh += f" 近3日有{b['mentions']}篇專家文章提及" + ("（正面）。" if b.get("pos", 0) > b.get("neg", 0) else "。")
        out.append({
            "name": p["name"], "pos": p["pos"], "nba": p["team"], "status": p.get("status", ""),
            "score": round(score, 2), "buzz": round(bscore, 2), "help": weak_top,
            "recent": {c["name"]: p["recent"].get(c["name"], 0) for c in cats},
            "season": {c["name"]: p["season"].get(c["name"], 0) for c in cats},
            "drop": drop["name"] if drop else None,
            "links": b.get("links", [])[:2],
            "reason": _t(en, zh),
        })
    return out


def trade_ideas(team, others, cats, zs, tz_all, totals_all, n=3):
    """Best 2-for-... style 1-for-1 swaps judged by the change in both teams' category scores."""
    base_me = totals_all[team["key"]]
    ideas = []
    mine = sorted(team["players"], key=lambda p: -p["_v"])
    my_pool = [p for p in mine[2:9] if _active(p)]          # keep my two best players
    for o in others:
        their = sorted(o["players"], key=lambda p: -p["_v"])
        their_pool = [p for p in their[:8] if _active(p)]
        best = None
        for a in my_pool:
            for b in their_pool:
                if b["_v"] < a["_v"] - 1.5 or b["_v"] > a["_v"] + 3.5:
                    continue
                new_me = _swap_total(team, a, b, cats, zs)
                new_ot = _swap_total(o, b, a, cats, zs)
                d_me = _delta(base_me, new_me, totals_all, cats)
                d_ot = _delta(totals_all[o["key"]], new_ot, totals_all, cats)
                if d_me <= 0.08 or d_ot < -0.04:
                    continue
                s = d_me + 0.5 * min(d_ot, 0.5)
                if not best or s > best[0]:
                    best = (s, a, b, d_me, d_ot, new_me, new_ot)
        if best:
            s, a, b, d_me, d_ot, new_me, new_ot = best
            gain = sorted(cats, key=lambda c: -_cdelta(base_me, new_me, totals_all, c))[:2]
            loss = sorted(cats, key=lambda c: _cdelta(base_me, new_me, totals_all, c))[:1]
            gn = [c["name"] for c in gain if _cdelta(base_me, new_me, totals_all, c) > 0.01]
            ls = [c["name"] for c in loss if _cdelta(base_me, new_me, totals_all, c) < -0.03]
            their_gain = [c["name"] for c in sorted(cats, key=lambda c: -_cdelta(totals_all[o['key']], new_ot, totals_all, c))[:2]
                          if _cdelta(totals_all[o['key']], new_ot, totals_all, c) > 0.01]
            en = (f"Ask {o['name']} for {b['name']} in exchange for {a['name']}. You gain {cat_list(gn, 'en') or 'depth'}"
                  f"{' and give up a little ' + cat_list(ls, 'en') if ls else ''}. "
                  f"They receive {cat_list(their_gain, 'en') or 'roster balance'}, keeping the deal roughly balanced.")
            zh = (f"向「{o['name']}」索取 {b['name']}，用 {a['name']} 交換。你增加{cat_list(gn, 'zh') or '陣容深度'}"
                  f"{'，略減' + cat_list(ls, 'zh') if ls else ''}。"
                  f"對方獲得{cat_list(their_gain, 'zh') or '陣容平衡'}，交易大致平衡。")
            ideas.append({"partner": o["name"], "partner_key": o["key"], "give": a["name"], "get": b["name"],
                          "give_pos": a["pos"], "get_pos": b["pos"], "my_gain": round(d_me, 2),
                          "their_gain": round(d_ot, 2), "gain_cats": gn, "loss_cats": ls,
                          "reason": _t(en, zh), "score": round(s, 2)})
    ideas.sort(key=lambda x: -x["score"])
    return ideas[:n]


def _swap_total(team, give, get, cats, zs):
    players = [p for p in team["players"] if p["id"] != give["id"]] + [get]
    return team_totals(players, cats, zs)


def _phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _cdelta(old, new, totals_all, c):
    """Change in expected win-rate (vs an average opponent) in category c.
    Saturated categories (already dominant) add little; categories near the middle add the most,
    so swapping surplus for need can help both sides."""
    vals = [t[c["name"]] for t in totals_all.values()]
    m, s = st.mean(vals), (st.pstdev(vals) or 1.0)
    sign = -1 if c["lower_better"] else 1
    zo, zn = sign * (old[c["name"]] - m) / s, sign * (new[c["name"]] - m) / s
    return _phi(zn) - _phi(zo)


def _delta(old, new, totals_all, cats):
    return sum(_cdelta(old, new, totals_all, c) for c in cats)


# ------------------------------------------------------------------ team narrative
def narrative(team, rank, n, sc, cat_rank, cats):
    order = sorted(cats, key=lambda c: -sc[c["name"]])
    strong = [c["name"] for c in order[:3] if sc[c["name"]] > 0]
    weak = [c["name"] for c in order[::-1][:3] if sc[c["name"]] < 0]
    pos = [p["pos"] for p in team["players"] if _active(p)]
    bigs = sum(1 for p in team["players"] if any(b in p["pos"] for b in BIGS) and _active(p))
    inj = [p["name"] for p in team["players"] if p.get("status") in ("INJ", "O")]
    adv_en, adv_zh, dis_en, dis_zh = [], [], [], []
    for c in strong:
        adv_en.append(f"{cat_label(c, 'en')}: projected #{cat_rank[c]} of {n} teams")
        adv_zh.append(f"{cat_label(c, 'zh')}：預測全聯盟第{cat_rank[c]}（共{n}隊）")
    for c in weak:
        dis_en.append(f"{cat_label(c, 'en')}: only #{cat_rank[c]} of {n} teams")
        dis_zh.append(f"{cat_label(c, 'zh')}：僅全聯盟第{cat_rank[c]}（共{n}隊）")
    if bigs <= 3 and cats:
        dis_en.append(f"Thin at centre/power forward ({bigs} healthy bigs)")
        dis_zh.append(f"中鋒／大前鋒人手單薄（健康內線僅{bigs}人）")
    elif bigs >= 7:
        adv_en.append(f"Deep frontcourt ({bigs} bigs) – a good source of trade chips")
        adv_zh.append(f"內線深度充足（{bigs}名內線），可作交易籌碼")
    if inj:
        dis_en.append("Injured / out: " + ", ".join(inj[:4]))
        dis_zh.append("傷缺球員：" + "、".join(inj[:4]))
    summary_en = (f"Projected #{rank} of {n}. Strong in {cat_list(strong, 'en') or 'no category'}; "
                  f"weak in {cat_list(weak, 'en') or 'no category'}.")
    summary_zh = (f"預測排名第{rank}（共{n}隊）。強項：{cat_list(strong, 'zh') or '無'}；"
                  f"弱項：{cat_list(weak, 'zh') or '無'}。")
    return {"strong": strong, "weak": weak, "summary": _t(summary_en, summary_zh),
            "advantages": _t(adv_en, adv_zh), "disadvantages": _t(dis_en, dis_zh)}


# ------------------------------------------------------------------ league driver
def analyse_league(lg, buzz):
    cats = lg["categories"]
    teams = lg["teams"]
    fa = lg["free_agents"]
    everyone = [p for t in teams for p in t["players"]] + fa
    zs = _zstats(everyone, cats)
    for p in everyone:
        p["_v"] = player_value(p, cats, zs)
    totals = {t["key"]: team_totals(t["players"], cats, zs) for t in teams}
    scores = _team_scores(totals, cats)
    overall = {k: sum(v.values()) for k, v in scores.items()}
    order = sorted(teams, key=lambda t: -overall[t["key"]])
    rank_of = {t["key"]: i + 1 for i, t in enumerate(order)}
    n = len(teams)
    cat_rank = {c["name"]: {} for c in cats}
    for c in cats:
        srt = sorted(teams, key=lambda t: -scores[t["key"]][c["name"]])
        for i, t in enumerate(srt):
            cat_rank[c["name"]][t["key"]] = i + 1

    out_teams, mine = [], None
    for t in order:
        k = t["key"]
        others = [o for o in teams if o["key"] != k]
        tz = scores[k]
        nar = narrative(t, rank_of[k], n, tz, {c["name"]: cat_rank[c["name"]][k] for c in cats}, cats)
        picks = fa_picks(t, fa, cats, zs, tz, 10 if t["mine"] else 3, buzz)
        trades = trade_ideas(t, others, cats, zs, scores, totals, 3 if t["mine"] else 2)
        roster = [{"name": p["name"], "pos": p["pos"], "nba": p["team"], "status": p.get("status", ""),
                   "value": round(p["_v"], 2), "season": p["season"]}
                  for p in sorted(t["players"], key=lambda p: -p["_v"])]
        entry = {"key": k, "name": t["name"], "mine": t["mine"], "yahoo_rank": t.get("rank"),
                 "record": t.get("record"), "proj_rank": rank_of[k], "score": round(overall[k], 2),
                 "totals": {c: round(v, 3) for c, v in totals[k].items()},
                 "cat_rank": {c["name"]: cat_rank[c["name"]][k] for c in cats},
                 "cat_z": {c: round(v, 2) for c, v in tz.items()},
                 "analysis": nar, "pickups": picks, "trades": trades, "roster": roster}
        out_teams.append(entry)
        if t["mine"]:
            mine = entry
    return {"key": lg["league_key"], "name": lg["name"], "season": lg["season"],
            "categories": [c["name"] for c in cats], "teams": out_teams, "n_teams": n,
            "mine": mine["key"] if mine else None,
            "waiver_top10": mine["pickups"] if mine else [],
            "my_trades": mine["trades"] if mine else []}


def analyse_all(leagues, buzz):
    return [analyse_league(lg, buzz) for lg in leagues]
