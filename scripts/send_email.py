"""Send the daily bilingual pickup email (target: 2:30pm HKT = 06:30 UTC).

Secrets (GitHub Actions): SMTP_USER, SMTP_PASS  [optional: SMTP_HOST, SMTP_PORT, MAIL_TO]
Default: Yahoo SMTP (smtp.mail.yahoo.com:465) using a Yahoo *app password* sent to yourself.
Usage: python scripts/send_email.py [--wait-until HH:MM(UTC)] [--dry-run]
"""
import html
import os
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from common import DATA, MAIL_TO_DEFAULT, cat_list, load

SITE = os.environ.get("SITE_URL", "https://kobee2321.github.io/fantasy-basketball-app/")


def build(latest):
    e = html.escape
    parts = [f"<h2>NBA fantasy pickups / 每日撿人建議</h2>",
             f"<p style='color:#666'>{e(latest['generated_hkt'])} · <a href='{SITE}'>Open dashboard / 開啟網站</a></p>"]
    if latest.get("demo"):
        parts.append("<p style='background:#fff3cd;padding:8px'><b>DEMO DATA</b> – Yahoo is not connected yet "
                     "/ 示範數據，尚未連接 Yahoo。</p>")
    for lg in latest["leagues"]:
        parts.append(f"<h3>{e(lg['name'])}</h3><ol>")
        for p in lg["waiver_top10"]:
            drop = (f" &nbsp;<i>drop / 可放棄: {e(p['drop'])}</i>" if p.get("drop") else "")
            parts.append(f"<li><b>{e(p['name'])}</b> ({e(p['pos'])})<br>{e(p['reason']['en'])}<br>"
                         f"<span style='color:#555'>{e(p['reason']['zh'])}</span>{drop}</li>")
        parts.append("</ol>")
        if lg["my_trades"]:
            t = lg["my_trades"][0]
            parts.append(f"<p><b>Trade idea / 交易建議:</b> {e(t['reason']['en'])}<br>"
                         f"<span style='color:#555'>{e(t['reason']['zh'])}</span></p>")
    parts.append("<p style='color:#999;font-size:12px'>Waivers process at 3:30pm HKT. Based on Yahoo stats and "
                 "expert articles from the last 3 days.</p>")
    return "".join(parts)


def wait_until(hhmm):
    h, m = map(int, hhmm.split(":"))
    now = datetime.now(timezone.utc)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    secs = (target - now).total_seconds()
    if 0 < secs <= 40 * 60:
        print(f"waiting {int(secs)}s until {hhmm} UTC")
        time.sleep(secs)


def main():
    latest = load(os.path.join(DATA, "latest.json"))
    if not latest:
        sys.exit("data/latest.json missing")
    body = build(latest)
    if "--dry-run" in sys.argv:
        with open(os.path.join(DATA, "email_preview.html"), "w", encoding="utf-8") as f:
            f.write(body)
        print("preview written")
        return
    if "--wait-until" in sys.argv:
        wait_until(sys.argv[sys.argv.index("--wait-until") + 1])
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if not (user and pw):
        sys.exit("SMTP_USER / SMTP_PASS not set – email skipped")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"NBA pickups {latest['generated_hkt'][:10]} / 今日撿人建議"
    msg["From"] = user
    msg["To"] = os.environ.get("MAIL_TO", MAIL_TO_DEFAULT)
    msg.attach(MIMEText(body, "html", "utf-8"))
    host, port = os.environ.get("SMTP_HOST", "smtp.mail.yahoo.com"), int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print("email sent to", msg["To"])


if __name__ == "__main__":
    main()
