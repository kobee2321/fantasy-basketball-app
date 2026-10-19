"""Shared helpers + bilingual (English / Traditional Chinese) vocabulary."""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IMPORT_DIR = os.path.join(DATA, "import")

MY_TEAM = os.environ.get("MY_TEAM_NAME", "shatin happy milan")
MAIL_TO_DEFAULT = "kobee2321@yahoo.com"

CAT_ZH = {
    "PTS": "得分", "REB": "籃板", "AST": "助攻", "STL": "搶斷", "BLK": "阻攻",
    "3PTM": "三分球", "3PM": "三分球", "FG%": "投籃命中率", "FT%": "罰球命中率",
    "3P%": "三分命中率", "TO": "失誤", "FPTS": "總得分", "OREB": "進攻籃板",
    "DREB": "防守籃板", "FGM": "投籃命中", "FTM": "罰球命中", "A/T": "助攻失誤比",
    "DD": "雙雙", "TD": "三雙",
}


def cat_label(c, lang):
    return CAT_ZH.get(c, c) if lang == "zh" else c


def cat_list(cats, lang):
    sep = "、" if lang == "zh" else ", "
    return sep.join(cat_label(c, lang) for c in cats)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("-", " ").replace(".", "").replace("'", "").replace("’", "")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
