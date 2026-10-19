# Fantasy Hoops Hub 🏀

Static site (GitHub Pages) + daily GitHub Action for your Yahoo NBA fantasy leagues.
Site: https://kobee2321.github.io/fantasy-basketball-app/

| # | Feature | Where |
|---|---------|-------|
| 1 | Team ranking with projected stats (top-10 players per team, category z-scores, heat-map) | **Team ranking** tab |
| 2 | Per-team analysis in **English / 繁體中文 / both**: strengths, weaknesses, category bars, waiver / free-agent and trade suggestions, roster | **Team analysis** tab |
| 3 | Daily **top 10 pickups** for *shatin happy milan* (recent form + your category needs + article buzz), with suggested drop | **Waiver top 10** tab |
| 4 | Reads NBA news/expert RSS feeds (last 3 days) + Yahoo stats, emails the pickups **every day 2:30pm HKT** | Action + `scripts/send_email.py` |
| 5 | Trade suggestions for *shatin happy milan* in every league (partner, give/get, reason, both-sides impact) | **My trades** tab |

Everything is rule-based (no paid AI service). Until Yahoo is connected the site shows clearly-labelled **DEMO DATA**.

## Set-up (about 15 minutes)

1. **Upload** these files to the repo root (keep the folder structure, including the hidden `.github` folder), then *Settings → Pages → Deploy from branch → main / (root)*.
2. **Yahoo app**: https://developer.yahoo.com/apps/ → Create app → permission *Fantasy Sports: Read*, redirect URI `oob`.
3. On your computer: `pip install requests` then `python scripts/get_token.py CLIENT_ID CLIENT_SECRET`, sign in with kobee2321@yahoo.com, paste the code → you get `YAHOO_REFRESH_TOKEN`.
4. **Email**: create a Yahoo *app password* (Yahoo Account Security → Generate app password). It sends from your Yahoo address to itself.
5. Repo *Settings → Secrets and variables → Actions* → add:
   `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`, `YAHOO_REFRESH_TOKEN`, `SMTP_USER` (kobee2321@yahoo.com), `SMTP_PASS` (app password).
   Optional: `MAIL_TO`, `SMTP_HOST`, `SMTP_PORT`.
6. *Actions → Daily update + email → Run workflow*. After it finishes, reload the site.
7. Check the first live run: `python scripts/yahoo_api.py --probe` shows raw Yahoo output if anything looks off.

The workflow runs daily at 13:45 HKT (05:45 UTC), refreshes the data, then **waits until 14:30 HKT** before sending the email, so it lands before the 3:30pm HKT waiver run. (GitHub may start scheduled jobs a few minutes late.)

## No Yahoo API access?
Copy `data/import/leagues.example.json` to `data/import/leagues.json`, fill in your leagues/rosters/free agents (per-game stats), commit. Same analysis, manual data.

## How the numbers work
- **Player value** = sum of category z-scores (per-game) across every rostered + free-agent player in the league.
- **Team projection** = top-10 healthy players' totals per category → z-score vs other teams → ranked.
- **Pickup score** = 40% season + 60% last-30-day z-scores, weighted toward your weak categories, + article buzz (names in RSS headlines/summaries, last 3 days, with positive/negative keyword scoring).
- **Trades** = 1-for-1 swaps scored by change in *expected category wins* (a normal-CDF model: gains in mid-pack categories matter more than piling onto a category you already dominate), requiring your gain > 0.08 and no meaningful loss for the partner. Your two best players are never offered.
- "Projected" stats are Yahoo's current per-game averages (last season's until the new season has games). Yahoo's API does not expose its own projections.

## Files
`index.html, style.css, app.js` site · `data/latest.json, data/articles.json` generated · `scripts/` Python pipeline · `.github/workflows/daily.yml` schedule · `tests/test_parsers.py` offline tests (`python tests/test_parsers.py`).

## Privacy
A public repo publishes `data/latest.json` (your league names, rosters). Never commit tokens: they live only in GitHub Secrets. Use a private repo if you don't want rosters public (Pages on private repos needs a paid GitHub plan).
