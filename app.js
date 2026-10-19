"use strict";
/* Fantasy Hoops Hub – static front-end. Reads data/latest.json (+ data/articles.json) produced by the daily GitHub Action. */
const UI = {
  title: { en: "Fantasy Hoops Hub", zh: "籃球夢幻中心" },
  rank: { en: "Team ranking", zh: "球隊排名" },
  team: { en: "Team analysis", zh: "球隊分析" },
  trades: { en: "My trades", zh: "交易建議" },
  waiver: { en: "Waiver top 10", zh: "撿人 Top 10" },
  articles: { en: "Articles", zh: "專家文章" },
  setup: { en: "Setup & status", zh: "設定與狀態" },
};
const CAT_ZH = { PTS: "得分", REB: "籃板", AST: "助攻", STL: "搶斷", BLK: "阻攻", "3PTM": "三分球", "3PM": "三分球", "FG%": "投籃命中率", "FT%": "罰球命中率", TO: "失誤", FPTS: "總得分" };
const TABS = ["rank", "team", "trades", "waiver", "articles", "setup"];
const S = { data: null, articles: null, li: 0, tab: "rank", lang: "en", team: null };

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };
const T = o => S.lang === "both" ? `${esc(o.en)}<span class="zh blk">${esc(o.zh)}</span>` : esc(o[S.lang]);
const I = o => S.lang === "both" ? `${esc(o.en)}<span class="zh il">${esc(o.zh)}</span>` : esc(o[S.lang]);
const L = (en, zh) => I({ en, zh });
const cat = c => S.lang === "zh" ? (CAT_ZH[c] || c) : S.lang === "both" ? (CAT_ZH[c] ? `${c} ${CAT_ZH[c]}` : c) : c;
const cats = list => (list || []).map(cat).join(S.lang === "zh" ? "、" : ", ");
const fmt = (v, c) => c.endsWith("%") ? Number(v).toFixed(3).replace(/^0/, "") : Number(v).toFixed(1);
const lg = () => S.data.leagues[S.li];
const me = l => l.teams.find(t => t.mine) || l.teams[0];

async function load() {
  try {
    const r = await fetch("data/latest.json?" + Date.now());
    S.data = await r.json();
  } catch (e) { document.getElementById("view").innerHTML = `<div class="card">Could not load data/latest.json. Run the “Daily update” GitHub Action once.</div>`; return; }
  try { S.articles = await (await fetch("data/articles.json?" + Date.now())).json(); } catch { S.articles = null; }
  S.lang = ["en", "zh", "both"].includes(store.get("lang")) ? store.get("lang") : "en";
  const sel = document.getElementById("league");
  sel.innerHTML = S.data.leagues.map((l, i) => `<option value="${i}">${esc(l.name)}</option>`).join("");
  sel.onchange = () => { S.li = +sel.value; S.team = null; render(); };
  document.querySelectorAll("#lang button").forEach(b => b.onclick = () => { S.lang = b.dataset.lang; store.set("lang", S.lang); render(); });
  const h = location.hash.slice(1); if (TABS.includes(h)) S.tab = h;
  render();
}

function render() {
  document.documentElement.lang = S.lang === "zh" ? "zh-Hant" : "en";
  document.querySelectorAll("#lang button").forEach(b => b.classList.toggle("on", b.dataset.lang === S.lang));
  document.querySelector("[data-i=title]").innerHTML = S.lang === "zh" ? UI.title.zh : UI.title.en;
  document.getElementById("tabs").innerHTML = TABS.map(t => `<button class="${t === S.tab ? "on" : ""}" data-t="${t}">${I(UI[t])}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => { S.tab = b.dataset.t; location.hash = S.tab; render(); });
  const d = S.data;
  document.getElementById("banner").innerHTML = d.demo ? `<div class="banner"><b>DEMO DATA</b> – ${L("synthetic players and stats, shown until Yahoo is connected (see Setup).", "示範用的模擬數據，連接 Yahoo 後會自動換成真實數據（見「設定與狀態」）。")}</div>` : "";
  document.getElementById("foot").innerHTML = `${L("Updated", "更新時間")}: ${esc(d.generated_hkt)} · ${L("source", "來源")}: ${esc(d.source)}`;
  const v = document.getElementById("view");
  
  v.innerHTML = { rank: vRank, team: vTeam, trades: vTrades, waiver: vWaiver, articles: vArticles, setup: vSetup }[S.tab]();
  if (S.tab === "team") { const s = document.getElementById("teamsel"); if (s) s.onchange = () => { S.team = s.value; render(); }; }
}

function heat(z) { const a = Math.min(Math.abs(z) / 2, 1) * 0.35; return z >= 0 ? `rgba(15,138,75,${a})` : `rgba(198,40,40,${a})`; }

function vRank() {
  const l = lg(), cs = l.categories;
  const rows = [...l.teams].sort((a, b) => a.proj_rank - b.proj_rank).map(t => `
    <tr class="${t.mine ? "me" : ""}"><td>${t.proj_rank}</td><td class="l">${esc(t.name)}${t.mine ? " ⭐" : ""}</td>
    <td>${t.score.toFixed(1)}</td>${cs.map(c => `<td style="background:${heat(t.cat_z[c])}">${fmt(t.totals[c], c)}</td>`).join("")}
    <td>${esc(t.record || "")}</td></tr>`).join("");
  return `<h2>${L("Projected team ranking", "球隊預測排名")}</h2>
  <p class="sub">${L("Each team's top-10 players' projected per-game totals; green = better than the league average, red = worse. Score = sum of category z-scores.", "以各隊最強10名球員的每場預測數據合計；綠色＝優於聯盟平均，紅色＝低於平均。分數為各項統計 z-score 總和。")}</p>
  <div class="tablewrap"><table><thead><tr><th>#</th><th class="l">${L("Team", "球隊")}</th><th>${L("Score", "分數")}</th>${cs.map(c => `<th>${cat(c)}</th>`).join("")}<th>${L("Record", "戰績")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function catBars(t, cs) {
  return cs.map(c => { const z = t.cat_z[c], w = Math.round(Math.min(Math.abs(z) / 2.5, 1) * 100); return `<div class="catrow"><span>${cat(c)}</span><div class="bar2"><i style="width:${w}%;background:${z >= 0 ? "var(--good)" : "var(--bad)"}"></i></div><span class="muted">#${t.cat_rank[c]}</span></div>`; }).join("");
}

function pickHtml(p, i, cs) {
  return `<div class="pick"><span class="rk">${i + 1}</span><b>${esc(p.name)}</b> <span class="muted">${esc(p.pos)} ${esc(p.nba)}</span>
  ${p.help.map(h => `<span class="pill g">${cat(h)}</span>`).join("")}
  <div>${T(p.reason)}</div>
  ${p.drop ? `<div class="muted">${L("Possible drop", "可考慮放棄")}: ${esc(p.drop)}</div>` : ""}
  ${(p.links || []).map(a => `<div class="muted">📰 <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a> (${esc(a.source)})</div>`).join("")}</div>`;
}

function tradeHtml(t) {
  return `<div class="pick"><b>${esc(t.give)}</b> ⇄ <b>${esc(t.get)}</b> <span class="muted">· ${L("partner", "對象")}: ${esc(t.partner)}</span>
  <div>${T(t.reason)}</div>
  <div class="muted">${L("Your gain", "你的收益")}: +${t.my_gain.toFixed(2)} · ${L("their gain", "對方收益")}: ${t.their_gain >= 0 ? "+" : ""}${t.their_gain.toFixed(2)} ${L("(expected category wins/week)", "（預期每週多贏類別數）")}</div></div>`;
}

function vTeam() {
  const l = lg(), cs = l.categories;
  const t = l.teams.find(x => x.key === S.team) || me(l);
  const opts = [...l.teams].sort((a, b) => a.proj_rank - b.proj_rank).map(x => `<option value="${esc(x.key)}" ${x.key === t.key ? "selected" : ""}>#${x.proj_rank} ${esc(x.name)}${x.mine ? " ⭐" : ""}</option>`).join("");
  const an = t.analysis;
  const list = o => `<ul class="clean">${o.en.map((_, i) => `<li>${T({ en: o.en[i], zh: o.zh[i] })}</li>`).join("") || "<li>–</li>"}</ul>`;
  return `<h2>${esc(t.name)} ${t.mine ? "⭐" : ""}</h2>
  <p class="sub"><select id="teamsel">${opts}</select></p>
  <div class="card">${T(an.summary)}</div>
  <div class="grid">
    <div class="card"><h3>${L("Advantages", "優勢")}</h3>${list(an.advantages)}</div>
    <div class="card"><h3>${L("Disadvantages", "劣勢")}</h3>${list(an.disadvantages)}</div>
    <div class="card"><h3>${L("Category strength (vs league)", "各項統計強弱（對比聯盟）")}</h3>${catBars(t, cs)}</div>
  </div>
  <div class="grid">
    <div class="card"><h3>${L("Waiver / free-agent suggestions", "撿人／自由球員建議")}</h3>${t.pickups.slice(0, t.mine ? 5 : 3).map((p, i) => pickHtml(p, i, cs)).join("") || "–"}</div>
    <div class="card"><h3>${L("Trade suggestions", "交易建議")}</h3>${t.trades.map(tradeHtml).join("") || "–"}</div>
  </div>
  <h3>${L("Roster", "陣容")}</h3>
  <div class="tablewrap"><table><thead><tr><th class="l">${L("Player", "球員")}</th><th class="l">${L("Pos", "位置")}</th><th>${L("Value", "價值")}</th>${cs.map(c => `<th>${cat(c)}</th>`).join("")}</tr></thead><tbody>
  ${t.roster.map(p => `<tr><td class="l">${esc(p.name)} ${p.status ? `<span class="pill b">${esc(p.status)}</span>` : ""}</td><td class="l">${esc(p.pos)}</td><td>${p.value.toFixed(1)}</td>${cs.map(c => `<td>${fmt(p.season[c] ?? 0, c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function vTrades() {
  const l = lg();
  return `<h2>${L("Trade suggestions for", "交易建議：")} ${esc(me(l).name)}</h2>
  <p class="sub">${L("1-for-1 swaps that raise your expected weekly category wins while staying balanced for the partner. Always check injuries and roster slots before proposing.", "一換一交易：提升你每週預期贏的類別數，同時讓對方大致平衡。提出前請先確認傷病與陣容空位。")}</p>
  ${S.data.leagues.map((x, i) => `<div class="card"><h3>${esc(x.name)} ${i === S.li ? "" : ""}</h3>${x.my_trades.map(tradeHtml).join("") || "–"}</div>`).join("")}`;
}

function vWaiver() {
  const l = lg();
  return `<h2>${L("Waiver top 10", "撿人 Top 10")} – ${esc(l.name)}</h2>
  <p class="sub">${L("Ranked by recent form, your category needs and expert-article buzz (last 3 days). Yahoo waivers process 3:30pm HKT; the daily email goes out at 2:30pm HKT.", "按近期表現、你的類別需要及專家文章（近3日）熱度排序。Yahoo 於香港時間下午3:30處理，每日電郵於下午2:30發出。")}</p>
  <div class="card">${l.waiver_top10.map((p, i) => pickHtml(p, i, l.categories)).join("") || "–"}</div>`;
}

function vArticles() {
  const a = S.articles;
  if (!a) return `<div class="card">${L("No article data yet.", "暫無文章數據。")}</div>`;
  return `<h2>${L("Expert articles & news (last 3 days)", "專家文章與新聞（近3日）")}</h2>
  <p class="sub">${a.count} ${L("items read", "篇已閱讀")}${a.errors.length ? ` · ${a.errors.length} ${L("feed(s) unreachable", "個來源無法讀取")}` : ""}</p>
  <div class="card">${a.articles.map(x => `<div class="pick"><a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}</a> <span class="muted">${esc(x.source)} · ${esc((x.date || "").slice(0, 10))}</span></div>`).join("") || "–"}</div>`;
}

function vSetup() {
  const d = S.data;
  return `<h2>${L("Setup & status", "設定與狀態")}</h2>
  <div class="card"><b>${L("Data source", "數據來源")}:</b> ${esc(d.source)} · ${esc(d.generated_hkt)}
  ${d.feed_errors.length ? `<div class="muted">${L("Unreachable feeds", "無法讀取的來源")}: ${esc(d.feed_errors.join(" | "))}</div>` : ""}</div>
  <div class="card"><h3>${L("Connect Yahoo (one time)", "連接 Yahoo（只需一次）")}</h3><ol>
  <li>${L("Create an app at developer.yahoo.com/apps (Fantasy Sports → Read, redirect URI", "到 developer.yahoo.com/apps 建立 App（Fantasy Sports → Read，redirect URI 填")} <code>oob</code>).</li>
  <li>${L("Run", "在電腦執行")} <code>python scripts/get_token.py CLIENT_ID CLIENT_SECRET</code> ${L("and sign in as your Yahoo account.", "並以你的 Yahoo 帳戶登入授權。")}</li>
  <li>${L("Add repo secrets", "在 GitHub 儲存庫加入 Secrets")}: <code>YAHOO_CLIENT_ID</code>, <code>YAHOO_CLIENT_SECRET</code>, <code>YAHOO_REFRESH_TOKEN</code>, <code>SMTP_USER</code>, <code>SMTP_PASS</code>.</li>
  <li>${L("Actions → “Daily update + email” → Run workflow.", "Actions →「Daily update + email」→ Run workflow。")}</li></ol>
  <p class="muted">${L("No Yahoo access? Put your leagues in data/import/leagues.json (see README) – same pipeline, manual data.", "未能連接 Yahoo？可把聯盟數據放入 data/import/leagues.json（見 README），流程相同。")}</p></div>`;
}

load();
