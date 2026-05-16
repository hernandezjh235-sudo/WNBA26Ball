# -*- coding: utf-8 -*-
# ============================================================
# WNBA PROP ENGINE — STREAMLIT SAFE FIX
# Loads fast first, then pulls real lines. No fake lines.
# Underdog-first, PrizePicks backup, full player cards, grading/learning/CLV.
# ============================================================

import os
import re
import json
import math
import difflib
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_VERSION = "WNBA v3.0 DYNAMIC WNBA NAME GUARD"

# =========================
# STORAGE
# =========================
STORAGE_DIR = os.getenv("STORAGE_DIR", "wnba_engine")
Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)

PICK_LOG = os.path.join(STORAGE_DIR, "official_pick_log.json")
RESULT_LOG = os.path.join(STORAGE_DIR, "graded_result_log.json")
LEARN_FILE = os.path.join(STORAGE_DIR, "player_learning.json")
CLV_FILE = os.path.join(STORAGE_DIR, "clv_tracker.json")
LINE_HISTORY_FILE = os.path.join(STORAGE_DIR, "line_history.json")
REQUEST_LOG_FILE = os.path.join(STORAGE_DIR, "request_log.json")
BEFORE_AFTER_FILE = os.path.join(STORAGE_DIR, "before_after_snapshots.json")

UNDERDOG_URLS = [
    "https://api.underdogfantasy.com/beta/v6/over_under_lines",
    "https://api.underdogfantasy.com/beta/v5/over_under_lines",
    "https://api.underdogfantasy.com/beta/v4/over_under_lines",
    "https://api.underdogfantasy.com/beta/v3/over_under_lines",
    "https://api.underdogfantasy.com/beta/v2/over_under_lines",
    "https://api.underdogfantasy.com/v1/over_under_lines",
]
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"

NBA_STATS_BASE = "https://stats.nba.com/stats"
WNBA_LEAGUE_ID = "10"

MARKET_LABELS = {
    "points": "Points",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "pts_rebs_asts": "Pts + Rebs + Asts",
    "pts_rebs": "Pts + Rebs",
    "pts_asts": "Pts + Asts",
    "rebs_asts": "Rebs + Asts",
    "threes": "3PT Made",
    "steals": "Steals",
    "blocks": "Blocks",
}

SUPPORTED_MARKETS = {
    "points": ["points", "pts"],
    "rebounds": ["rebounds", "rebs", "reb"],
    "assists": ["assists", "asts", "ast"],
    "pts_rebs_asts": ["pts+rebs+asts", "points+rebounds+assists", "pra", "pts + rebs + asts"],
    "pts_rebs": ["pts+rebs", "points+rebounds", "points + rebounds"],
    "pts_asts": ["pts+asts", "points+assists", "points + assists"],
    "rebs_asts": ["rebs+asts", "rebounds+assists", "rebounds + assists"],
    "threes": ["3-pointers made", "three pointers made", "3pt made", "3pm", "threes", "three pointers"],
    "steals": ["steals", "stls", "stl"],
    "blocks": ["blocks", "blks", "blk"],
}

MIN_PASS_SCORE = 78
MIN_PASS_PROB = 0.57
MIN_PASS_EDGE = 0.55
MIN_ELITE_SCORE = 88
MIN_ELITE_PROB = 0.62
MIN_ELITE_EDGE = 0.90
MAX_RECOMMENDED_KELLY = 0.02

LEARNING_MIN_SAMPLES = 4
LEARNING_RATE = 0.04
LEARNING_SCALE_MIN = 0.90
LEARNING_SCALE_MAX = 1.10

# =========================
# STREAMLIT CONFIG FIRST
# =========================
st.set_page_config(
    page_title="WNBA Prop Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {background:radial-gradient(circle at top left,#141827 0%,#07090f 42%,#020204 100%);color:#fff;}
.block-container {padding-top:1.0rem;max-width:1650px;}
.hero-panel {background:linear-gradient(135deg,rgba(30,38,72,.96),rgba(8,10,18,.98));border:1px solid rgba(128,162,255,.38);border-radius:26px;padding:22px;box-shadow:0 0 32px rgba(80,120,255,.16);margin-bottom:18px;}
.big-title {font-size:42px;font-weight:950;letter-spacing:-1px;}
.sub-title {color:#c7cfdf;font-size:15px;margin-top:-6px;}
.small-muted {color:#aeb6c8;font-size:13px;}
.clean-card {background:linear-gradient(145deg,#10131d,#090b12);border:1px solid rgba(145,170,255,.22);border-radius:20px;padding:18px;box-shadow:0 0 18px rgba(80,120,255,.08);margin-bottom:14px;}
.green-card {background:linear-gradient(145deg,#061c13,#07100c);border:1px solid rgba(0,255,145,.34);border-radius:20px;padding:18px;box-shadow:0 0 20px rgba(0,255,145,.13);margin-bottom:14px;}
.warn-card {background:linear-gradient(145deg,#211600,#100b02);border:1px solid rgba(255,195,70,.34);border-radius:20px;padding:18px;box-shadow:0 0 18px rgba(255,195,70,.10);margin-bottom:14px;}
.red-card {background:linear-gradient(145deg,#240808,#100404);border:1px solid rgba(255,90,90,.34);border-radius:20px;padding:18px;box-shadow:0 0 18px rgba(255,90,90,.10);margin-bottom:14px;}
.game-card {background:linear-gradient(145deg,#12182a,#080a12);border:1px solid rgba(145,170,255,.28);border-radius:18px;padding:14px;margin-bottom:10px;}
.badge {display:inline-block;padding:6px 11px;border-radius:999px;background:#141827;border:1px solid rgba(160,180,255,.38);color:#dce5ff;font-weight:850;margin:3px 4px 3px 0;}
.good-badge {background:#002818;border-color:rgba(0,255,145,.48);color:#b9ffdc;}
.yellow-badge {background:#2a1e00;border-color:rgba(255,210,70,.48);color:#ffe6a6;}
.red-badge {background:#2a0707;border-color:rgba(255,90,90,.48);color:#ffc4c4;}
.blue-badge {background:#111d38;border-color:rgba(128,162,255,.48);color:#dce5ff;}
.kpi-strip {display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:12px 0 18px 0;}
.kpi-box {background:linear-gradient(145deg,#10131d,#080a10);border:1px solid rgba(145,170,255,.24);border-radius:18px;padding:14px;min-height:92px;}
.kpi-label {font-size:12px;color:#aeb6c8;font-weight:850;letter-spacing:.04em;text-transform:uppercase;}
.kpi-value {font-size:25px;font-weight:950;color:#fff;margin-top:6px;}
.kpi-sub {font-size:12px;color:#c7cfdf;margin-top:5px;}
.stTabs [data-baseweb="tab"] {color:#b8c3cf;font-weight:850;}
.stTabs [aria-selected="true"] {color:#8db3ff!important;border-bottom:3px solid #8db3ff;}
[data-testid="stMetric"] {background:linear-gradient(145deg,#10131d,#080a10);border:1px solid rgba(145,170,255,.24);border-radius:18px;padding:13px;}
@media (max-width:1100px){.kpi-strip{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def tomorrow_str():
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

def safe_float(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default

def safe_int(x, default=None):
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    try:
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def log_source_request(source, status, message=""):
    rows = load_json(REQUEST_LOG_FILE, [])
    rows.append({"time": now_iso(), "source": str(source)[:220], "status": str(status)[:80], "message": str(message)[:500]})
    save_json(REQUEST_LOG_FILE, rows[-500:])

def strip_accents(text):
    try:
        return "".join(ch for ch in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(ch))
    except Exception:
        return str(text or "")

def normalize_name(name):
    s = strip_accents(name).lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    for suffix in [" jr", " sr", " ii", " iii", " iv"]:
        s = s.replace(suffix, " ")
    return " ".join(s.split())

def name_score(a, b):
    a_norm, b_norm = normalize_name(a), normalize_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.94
    ap, bp = a_norm.split(), b_norm.split()
    if ap and bp and ap[-1] == bp[-1] and ap[0][:1] == bp[0][:1]:
        return 0.93
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()

def safe_get_json(url, params=None, timeout=8, headers=None):
    try:
        h = {"User-Agent": "Mozilla/5.0 WNBAPropEngine/2.1", "Accept": "application/json,text/plain,*/*"}
        if headers:
            h.update(headers)
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        if r.status_code != 200:
            log_source_request(url, f"HTTP {r.status_code}", r.text[:300])
            return None
        return r.json()
    except Exception as e:
        log_source_request(url, "REQUEST_ERROR", str(e))
        return None

def flatten_json(obj):
    items = []
    if isinstance(obj, dict):
        items.append(obj)
        for v in obj.values():
            items.extend(flatten_json(v))
    elif isinstance(obj, list):
        for x in obj:
            items.extend(flatten_json(x))
    return items

def parse_prop_date_from_text_or_obj(obj):
    """Best-effort date extraction from prop-feed rows.

    Many public Underdog rows do not expose a clean game date field. If we cannot
    read a date, we keep the line visible on All Lines instead of hiding it.
    """
    if not isinstance(obj, dict):
        return None
    keys = [
        "scheduled_at", "starts_at", "start_time", "game_date", "date",
        "match_date", "commence_time", "event_time", "game_time"
    ]
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and len(v) >= 8:
            try:
                # Handles 2026-05-17, 2026-05-17T00:00:00Z, etc.
                return v[:10]
            except Exception:
                pass
    try:
        blob = json.dumps(obj, default=str)
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", blob)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def day_label_from_date(prop_date):
    if prop_date == today_str():
        return "Today"
    if prop_date == tomorrow_str():
        return "Tomorrow"
    if prop_date:
        return prop_date
    return "Unknown"

def has_bad_cross_sport_terms(text):
    raw = " " + str(text or "").lower() + " "
    bad_terms = [
        " mlb", " baseball", " pitcher", " strikeout", " strikeouts",
        " nfl", " football", " nhl", " hockey", " soccer", " tennis",
        " golf", " mma", " ufc", " ncaab", " ncaa", " college",
        " esports", " esport", " nascar", " dota", " dota 2", " counter-strike", " counter strike",
        " cs2", " csgo", " valorant", " league of legends", " lol esports", " gaming",
        " natus vincere", " xtreme gaming", " fnatic", " faze", " team liquid"
    ]
    return any(x in raw for x in bad_terms)

def object_mentions_other_basketball_league(text):
    raw = " " + str(text or "").lower() + " "
    # NBA rows sometimes say NBA explicitly. Block those unless the same object also says WNBA.
    if " wnba" in raw or " women" in raw or " women's" in raw:
        return False
    return " nba" in raw or " basketball_nba" in raw or " mens basketball" in raw or " men basketball" in raw


def ud_attrs(obj):
    """Return Underdog attrs merged with top-level fields."""
    if not isinstance(obj, dict):
        return {}
    out = {}
    attrs = obj.get("attributes")
    if isinstance(attrs, dict):
        out.update(attrs)
    for k, v in obj.items():
        if k not in ["attributes", "relationships", "included", "data"]:
            out.setdefault(k, v)
    return out

def underdog_object_key(obj):
    if not isinstance(obj, dict):
        return None
    oid = obj.get("id")
    typ = obj.get("type")
    if oid is None:
        return None
    return (str(typ or ""), str(oid))

def build_underdog_id_index(data):
    """Index every typed/id object so line rows can resolve player/market/league relationships."""
    idx = {}
    for obj in flatten_json(data):
        if not isinstance(obj, dict):
            continue
        key = underdog_object_key(obj)
        if key:
            idx[key] = obj
            # also keep id-only fallback because some relationships omit type
            idx[("", key[1])] = obj
    return idx

def relationship_refs(obj):
    refs = []
    if not isinstance(obj, dict):
        return refs
    rels = obj.get("relationships")
    if not isinstance(rels, dict):
        return refs

    def add_ref(x):
        if isinstance(x, dict):
            if "data" in x:
                add_ref(x.get("data"))
                return
            rid = x.get("id")
            typ = x.get("type")
            if rid is not None:
                refs.append((str(typ or ""), str(rid)))
        elif isinstance(x, list):
            for item in x:
                add_ref(item)

    for v in rels.values():
        add_ref(v)
    return refs

def combine_obj_and_related_text(obj, idx, depth=2):
    """Collect text from an Underdog object and its related objects."""
    seen = set()
    parts = []

    def walk(o, d):
        if not isinstance(o, dict) or d < 0:
            return
        key = underdog_object_key(o)
        if key and key in seen:
            return
        if key:
            seen.add(key)

        a = ud_attrs(o)
        for k, v in a.items():
            if isinstance(v, (str, int, float, bool)) and v not in [None, ""]:
                parts.append(f"{k}:{v}")
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, (str, int, float, bool)) and vv not in [None, ""]:
                        parts.append(f"{k}.{kk}:{vv}")

        # include a small JSON slice because some Underdog versions store names deep
        try:
            parts.append(json.dumps(o, default=str)[:1800])
        except Exception:
            pass

        for ref in relationship_refs(o):
            ro = idx.get(ref) or idx.get(("", ref[1]))
            if ro is not None:
                walk(ro, d - 1)

    walk(obj, depth)
    return " | ".join(parts)

def candidate_player_name_from_text_and_related(obj, idx):
    """Find a WNBA player name from direct player fields or market titles.

    v2.8 fix:
    Your logs showed market > 0 but name = 0. Underdog often stores names as
    titles like 'Aja Wilson Points'. Earlier versions rejected those because
    they contained market words. This version strips the market words and keeps
    the player name.
    """
    candidates = []

    def add_from(o):
        if not isinstance(o, dict):
            return
        a = ud_attrs(o)

        # First/last is strongest.
        fn = a.get("first_name")
        ln = a.get("last_name")
        if isinstance(fn, str) and isinstance(ln, str):
            candidates.append((fn + " " + ln).strip())

        # Direct name fields.
        for k in [
            "player_name", "athlete_name", "full_name", "display_name",
            "name", "abbr_name", "short_name"
        ]:
            v = a.get(k)
            if isinstance(v, str) and len(v.strip()) >= 3:
                candidates.append(v.strip())

        # Title fields that may include market name.
        for k in ["title", "display_title", "description", "over_under_title", "option_display"]:
            v = a.get(k)
            if isinstance(v, str):
                cleaned = strip_market_words_from_title(v)
                if cleaned:
                    candidates.append(cleaned)

    add_from(obj)
    for ref in relationship_refs(obj):
        ro = idx.get(ref) or idx.get(("", ref[1]))
        add_from(ro)
        if isinstance(ro, dict):
            for ref2 in relationship_refs(ro):
                ro2 = idx.get(ref2) or idx.get(("", ref2[1]))
                add_from(ro2)

    # Extra fallback: parse all related titles.
    tc = title_candidates_from_obj_and_related(obj, idx)
    if tc:
        candidates.append(tc)

    good = []
    for c in candidates:
        cc = str(c or "").strip()
        if not cc:
            continue

        # If direct field still has market words, strip them before rejecting.
        cleaned = strip_market_words_from_title(cc) or cc
        if is_bad_player_like_name(cleaned):
            continue

        # Avoid obvious generic market/team labels.
        low = cleaned.lower()
        if low in ["points", "rebounds", "assists", "steals", "blocks", "wnba"]:
            continue

        good.append(cleaned)

    if good:
        return sorted(set(good), key=lambda x: (len(x), x))[0]
    return None

def extract_underdog_line_from_obj_or_related(obj, idx, market=None, combined_text=""):
    """Find the numeric prop line from object, relationships, or readable text.

    v2.6 fix:
    Your logs showed market/name counts were positive but line=0. That means
    Underdog exposed the player and market, but the numeric line was not in the
    usual numeric JSON keys. This fallback scans related text too.
    """
    keys = [
        "stat_value", "line_score", "over_under_line", "target_value", "line",
        "value", "over_under", "total", "points", "line_value", "display_value",
        "option_line", "projection", "projected_value", "stat_line", "line_display"
    ]

    def scan_numeric_keys(o):
        if not isinstance(o, dict):
            return None
        a = ud_attrs(o)
        for k in keys:
            f = safe_float(a.get(k))
            if sane_wnba_line(market, f) is not None:
                return float(f)
        return None

    # 1) Numeric keys on object.
    line = scan_numeric_keys(obj)
    if line is not None:
        return line

    # 2) Numeric keys on related objects.
    for ref in relationship_refs(obj):
        ro = idx.get(ref) or idx.get(("", ref[1]))
        line = scan_numeric_keys(ro)
        if line is not None:
            return line
        if isinstance(ro, dict):
            for ref2 in relationship_refs(ro):
                ro2 = idx.get(ref2) or idx.get(("", ref2[1]))
                line = scan_numeric_keys(ro2)
                if line is not None:
                    return line

    # 3) Regex scan on combined object + related text.
    text_blob = str(combined_text or "")
    if not text_blob:
        try:
            text_blob = json.dumps(obj, default=str)
        except Exception:
            text_blob = ""

    raw_candidates = []

    # Prefer numbers near market words.
    market_words = {
        "points": r"(points|pts)",
        "rebounds": r"(rebounds|rebs|reb)",
        "assists": r"(assists|asts|ast)",
        "pts_rebs_asts": r"(pra|points\s*\+\s*rebounds\s*\+\s*assists|pts\s*\+\s*rebs\s*\+\s*asts)",
        "pts_rebs": r"(points\s*\+\s*rebounds|pts\s*\+\s*rebs)",
        "pts_asts": r"(points\s*\+\s*assists|pts\s*\+\s*asts)",
        "rebs_asts": r"(rebounds\s*\+\s*assists|rebs\s*\+\s*asts)",
        "threes": r"(3\s*pt|3pt|3pm|three|threes|3-pointers)",
        "steals": r"(steals|stls|stl)",
        "blocks": r"(blocks|blks|blk)",
    }

    mw = market_words.get(market, r"(points|rebounds|assists)")
    patterns = [
        rf"(?i)(\d{{1,2}}(?:\.5|\.0)?)\s*(?:{mw})",
        rf"(?i)(?:{mw})\D{{0,30}}(\d{{1,2}}(?:\.5|\.0)?)",
        r"(?<!\d)(\d{1,2}\.5)(?!\d)",
        r"(?<!\d)(\d{1,2}\.0)(?!\d)",
    ]

    for pat in patterns:
        for m in re.findall(pat, text_blob):
            if isinstance(m, tuple):
                m = next((x for x in m if x and re.search(r"\d", x)), "")
            f = safe_float(m)
            if sane_wnba_line(market, f) is not None:
                raw_candidates.append(float(f))

    if not raw_candidates:
        return None

    vals = sorted(set(raw_candidates))

    # Avoid selecting tiny unrelated numbers for points/combo markets if better high values exist.
    if market == "points":
        high = [v for v in vals if v >= 5.5]
        vals = high or vals
    elif market in ["pts_rebs_asts", "pts_rebs", "pts_asts"]:
        high = [v for v in vals if v >= 8.5]
        vals = high or vals

    return float(vals[len(vals)//2])

def sane_wnba_line(market, line):
    line = safe_float(line)
    if line is None:
        return None
    # Avoid metadata numbers like IDs, ranks, timestamps.
    ranges = {
        "points": (0.5, 45.5),
        "rebounds": (0.5, 22.5),
        "assists": (0.5, 16.5),
        "pts_rebs_asts": (3.5, 75.5),
        "pts_rebs": (2.5, 65.5),
        "pts_asts": (2.5, 60.5),
        "rebs_asts": (1.5, 35.5),
        "threes": (0.5, 7.5),
        "steals": (0.5, 5.5),
        "blocks": (0.5, 5.5),
    }
    lo, hi = ranges.get(market, (0.5, 80.0))
    if not (lo <= line <= hi):
        return None
    # Props can be whole on fantasy apps sometimes, but most are half. Allow both.
    return float(line)


def strip_market_words_from_title(title):
    """Turn titles like 'A'ja Wilson Points' into 'A'ja Wilson'."""
    if not isinstance(title, str):
        return None
    s = title.strip()
    if not s:
        return None

    # Remove common sportsbook separators/details.
    s = re.sub(r"(?i)\b(higher|lower|over|under|than|more|less)\b", " ", s)
    s = re.sub(r"(?i)\b(line|projection|fantasy score|stat)\b", " ", s)

    market_phrases = [
        "points + rebounds + assists", "pts + rebs + asts", "pts+rebs+asts",
        "points + rebounds", "pts + rebs", "pts+rebs",
        "points + assists", "pts + asts", "pts+asts",
        "rebounds + assists", "rebs + asts", "rebs+asts",
        "3-pointers made", "3 pointers made", "three pointers made",
        "made threes", "three pointers", "3pt made", "3pm",
        "points", "pts", "rebounds", "rebs", "reb", "assists", "asts", "ast",
        "steals", "stls", "stl", "blocks", "blks", "blk", "pra"
    ]
    for phrase in sorted(market_phrases, key=len, reverse=True):
        s = re.sub(r"(?i)\b" + re.escape(phrase).replace("\\ ", r"\s*") + r"\b", " ", s)

    # Remove line numbers from the title.
    s = re.sub(r"(?<!\d)\d{1,2}(?:\.5|\.0)?(?!\d)", " ", s)

    # Remove team/event pieces.
    s = re.split(r"(?i)\s+(?:vs\.?|@)\s+", s)[0]
    s = s.replace(":", " ")
    s = " ".join(s.split()).strip(" -|•")

    # Must look like a player name.
    if 2 <= len(s.split()) <= 4:
        bad = s.lower()
        if not any(x in bad for x in ["dota", "gaming", "esports", "team ", " vs ", " @ ", "natus", "vincere"]):
            return s
    return None

def title_candidates_from_obj_and_related(obj, idx):
    candidates = []

    def pull(o):
        if not isinstance(o, dict):
            return
        a = ud_attrs(o)
        for k in [
            "title", "display_title", "name", "display_name", "description",
            "over_under_title", "option_display", "appearance_stat"
        ]:
            v = a.get(k)
            if isinstance(v, str):
                cleaned = strip_market_words_from_title(v)
                if cleaned:
                    candidates.append(cleaned)

    pull(obj)
    for ref in relationship_refs(obj):
        ro = idx.get(ref) or idx.get(("", ref[1]))
        pull(ro)
        if isinstance(ro, dict):
            for ref2 in relationship_refs(ro):
                ro2 = idx.get(ref2) or idx.get(("", ref2[1]))
                pull(ro2)

    if candidates:
        return sorted(set(candidates), key=lambda x: (len(x), x))[0]
    return None

def is_bad_player_like_name(name):
    low = str(name or "").lower()
    if any(x in low for x in [
        "dota", "gaming", "natus", "vincere", "esports", "counter-strike",
        "cs2", "valorant", "league of legends", " vs ", " vs. ", " @ "
    ]):
        return True
    if ":" in str(name) or len(str(name).split()) > 4 or len(str(name).split()) < 2:
        return True
    return False


NBA_NAME_BLOCKLIST = {
    # Common NBA players that should never appear in WNBA board.
    "victor wembanyama", "nikola jokic", "luka doncic", "shai gilgeous alexander",
    "lebron james", "stephen curry", "kevin durant", "anthony edwards",
    "jayson tatum", "jaylen brown", "giannis antetokounmpo", "joel embiid",
    "jalen brunson", "donovan mitchell", "devin booker", "kyrie irving",
    "anthony davis", "tyrese haliburton", "ja morant", "trae young",
    "damian lillard", "paolo banchero", "cade cunningham", "zion williamson",
    "james harden", "kawhi leonard", "paul george", "lamelo ball",
    "bam adebayo", "domantas sabonis", "deaaron fox", "chet holmgren",
    "scottie barnes", "tyrese maxey", "mikal bridges", "jimmy butler",
    "jamal murray", "rudy gobert", "karl anthony towns", "jaren jackson jr",
}

WNBA_NAME_ALLOW_HINTS = {
    # Core WNBA names to protect the fallback parser from NBA slips.
    "aja wilson", "a ja wilson", "breanna stewart", "sabrina ionescu",
    "caitlin clark", "angel reese", "napheesa collier", "alyssa thomas",
    "kelsey plum", "jackie young", "chelsea gray", "arike ogunbowale",
    "nneka ogwumike", "jewell loyd", "skylar diggins", "kahleah copper",
    "diana taurasi", "brittney griner", "aliyah boston", "kelsey mitchell",
    "rhyne howard", "allisha gray", "dearica hamby", "rickea jackson",
    "azura stevens", "brionna jones", "dewanna bonner", "marina mabrey",
    "di jonai carrington", "dijonai carrington", "natasha cloud",
    "natasha howard", "sophie cunningham", "satou sabally", "maddy siegrist",
    "kayla mcbride", "courtney williams", "alanna smith", "diamond miller",
    "shakira austin", "brittney sykes", "aaliyah edwards", "elena delle donne",
    "gabby williams", "nneka ogwumike", "jonquel jones", "betnijah laney",
    "leonie fiebich", "nyara sabally", "teaira mccowan", "saniya rivers",
    "paige bueckers", "sonia citron", "kiki iriafen", "hailey van lith",
    "li yueru", "kate martin", "monique billings", "erica wheeler",
    "lexie hull", "victoria vivians", "na lyssa smith", "nalyssa smith",
    "temi fagbenle", "jordin canada", "cheyenne parker", "aari mcdonald",
    "zhalia mccall", "maya caldwell", "lexie brown", "rae burrell",
    "natalie achonwa", "elizabeth williams", "moriah jefferson",
}

def is_known_nba_name(name):
    n = normalize_name(name)
    if n in NBA_NAME_BLOCKLIST:
        return True
    # Obvious NBA-only surname protections for unique names.
    nba_unique_tokens = ["wembanyama", "jokic", "doncic", "gilgeous", "antetokounmpo"]
    return any(tok in n for tok in nba_unique_tokens)

def is_likely_wnba_name(name, combined_text=""):
    n = normalize_name(name)
    raw = " " + str(combined_text or "").lower() + " "
    if is_known_nba_name(name):
        return False
    if n in WNBA_NAME_ALLOW_HINTS:
        return True
    if " wnba" in raw or "women" in raw or "women's" in raw or "basketball_wnba" in raw:
        return True
    # If no explicit WNBA marker, do not accept random names from a mixed Underdog payload.
    return False


def extract_dynamic_wnba_names_from_payload(data):
    """Build WNBA player allowlist from Underdog's own WNBA-linked objects.

    This fixes logs where name/line are found but every row is rejected because
    the static WNBA list is incomplete.
    """
    names = set()
    objects = flatten_json(data)

    def add_name(v):
        if not isinstance(v, str):
            return
        cleaned = strip_market_words_from_title(v) or v.strip()
        if not cleaned:
            return
        if is_bad_player_like_name(cleaned):
            return
        if is_known_nba_name(cleaned):
            return
        # Avoid event/team strings
        low = cleaned.lower()
        if any(x in low for x in [" vs ", " vs. ", " @ ", "dota", "gaming", "esports"]):
            return
        if 2 <= len(cleaned.split()) <= 4:
            names.add(normalize_name(cleaned))

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        blob = json.dumps(obj, default=str).lower()
        if not ("wnba" in blob or "women" in blob or "women's" in blob or "basketball_wnba" in blob):
            continue
        a = ud_attrs(obj)
        fn = a.get("first_name")
        ln = a.get("last_name")
        if isinstance(fn, str) and isinstance(ln, str):
            add_name(fn + " " + ln)
        for k in [
            "player_name", "athlete_name", "full_name", "display_name", "name",
            "title", "display_title", "description", "over_under_title", "option_display"
        ]:
            add_name(a.get(k))
    return names

def is_likely_wnba_name_dynamic(name, combined_text="", dynamic_names=None):
    n = normalize_name(name)
    raw = " " + str(combined_text or "").lower() + " "
    if is_known_nba_name(name):
        return False
    if n in WNBA_NAME_ALLOW_HINTS:
        return True
    if dynamic_names and n in dynamic_names:
        return True
    if " wnba" in raw or "women" in raw or "women's" in raw or "basketball_wnba" in raw:
        return True
    return False

def underdog_text_is_wnba(text, payload_has_wnba=False):
    raw = " " + str(text or "").lower() + " "

    # Hard block obvious wrong sports even if the full Underdog payload has WNBA elsewhere.
    if has_bad_cross_sport_terms(raw):
        return False
    if object_mentions_other_basketball_league(raw):
        return False
    if any(x in raw for x in [" wembanyama", " lebron ", " doncic", " jokic", " gilgeous", " curry"]):
        return False

    # Strong accept when the related object chain itself says WNBA/women.
    if " wnba" in raw or " women" in raw or " women's" in raw or "basketball_wnba" in raw:
        return True

    # Payload-only fallback is allowed only later if the recovered name is WNBA allowlisted.
    if payload_has_wnba:
        basketball_markers = [" points", " rebounds", " assists", " pts", " rebs", " asts", " 3pt", "3pm"]
        return any(x in raw for x in basketball_markers)

    return False


# =========================
# BETTING MATH
# =========================
def decimal_odds(odds):
    odds = safe_float(odds)
    if odds is None:
        return None
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)

def expected_value(prob, odds=-110):
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return None
    return (prob * (dec - 1)) - (1 - prob)

def kelly_fraction(prob, odds=-110):
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return 0.0
    b = dec - 1
    q = 1 - prob
    if b <= 0:
        return 0.0
    return float(clamp(((b * prob) - q) / b, 0, 0.25))

def normal_side_probability(proj, line, std, side):
    proj = safe_float(proj)
    line = safe_float(line)
    std = max(safe_float(std, 1.0) or 1.0, 0.35)
    if proj is None or line is None:
        return None
    z = (line - proj) / std
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return float(clamp(1 - cdf if side == "OVER" else cdf, 0.001, 0.999))

# =========================
# STATS — SAFE OPTIONAL
# =========================
def nba_stats_headers():
    return {
        "Host": "stats.nba.com",
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, */*",
        "x-nba-stats-token": "true",
        "User-Agent": "Mozilla/5.0",
        "x-nba-stats-origin": "stats",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
    }

def stats_df_from_result(data, idx=0):
    try:
        result = data["resultSets"][idx]
        return pd.DataFrame(result["rowSet"], columns=result["headers"])
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def get_wnba_player_dashboard(season="2025", last_n="0"):
    url = f"{NBA_STATS_BASE}/leaguedashplayerstats"
    params = {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "",
        "GameSegment": "", "Height": "", "LastNGames": str(last_n), "LeagueID": WNBA_LEAGUE_ID,
        "Location": "", "MeasureType": "Base", "Month": "0", "OpponentTeamID": "0",
        "Outcome": "", "PORound": "0", "PaceAdjust": "N", "PerMode": "PerGame",
        "Period": "0", "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N",
        "Rank": "N", "Season": season, "SeasonSegment": "", "SeasonType": "Regular Season",
        "ShotClockRange": "", "StarterBench": "", "TeamID": "0", "TwoWay": "0",
        "VsConference": "", "VsDivision": "", "Weight": "",
    }
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=8)
    return stats_df_from_result(data)

@st.cache_data(ttl=900, show_spinner=False)
def get_wnba_scoreboard(date_str):
    url = f"{NBA_STATS_BASE}/scoreboardv2"
    mmddyyyy = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")
    params = {"DayOffset": "0", "GameDate": mmddyyyy, "LeagueID": WNBA_LEAGUE_ID}
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=8)
    games = stats_df_from_result(data, 0)
    linescore = stats_df_from_result(data, 1)
    out = []
    if games.empty:
        return out
    for _, g in games.iterrows():
        gid = str(g.get("GAME_ID", ""))
        home_id = g.get("HOME_TEAM_ID")
        away_id = g.get("VISITOR_TEAM_ID")
        home_name, away_name = str(home_id), str(away_id)
        if not linescore.empty and "GAME_ID" in linescore.columns:
            sub = linescore[linescore["GAME_ID"].astype(str) == gid]
            for _, lr in sub.iterrows():
                tid = lr.get("TEAM_ID")
                abbr = lr.get("TEAM_ABBREVIATION") or lr.get("TEAM_NAME") or ""
                if str(tid) == str(home_id):
                    home_name = abbr
                if str(tid) == str(away_id):
                    away_name = abbr
        out.append({"Game ID": gid, "Date": date_str, "Away": away_name, "Home": home_name, "Status": g.get("GAME_STATUS_TEXT", ""), "Time": str(g.get("GAME_DATE_EST", date_str))})
    return out

def lookup_player_stat(player_name, stats_df):
    if stats_df is None or stats_df.empty or not player_name:
        return None
    best, best_score = None, 0
    for _, r in stats_df.iterrows():
        sc = name_score(player_name, str(r.get("PLAYER_NAME", "")))
        if sc > best_score:
            best_score = sc
            best = r
    if best is None or best_score < 0.78:
        return None
    d = best.to_dict()
    d["_name_match_score"] = round(best_score, 3)
    return d

# =========================
# REAL PROP PARSERS
# =========================
def detect_market(text):
    t = str(text or "").lower().replace("-", " ").replace("_", " ")
    t = " ".join(t.split())
    if "fantasy" in t:
        return None
    for key, aliases in SUPPORTED_MARKETS.items():
        for alias in aliases:
            if alias.lower().replace("-", " ") in t:
                return key
    if "pts" in t and "reb" in t and "ast" in t:
        return "pts_rebs_asts"
    if "pts" in t and "reb" in t:
        return "pts_rebs"
    if "pts" in t and "ast" in t:
        return "pts_asts"
    if "reb" in t and "ast" in t:
        return "rebs_asts"
    return None

def extract_number_line(obj):
    for key in ["stat_value", "line", "value", "over_under", "target", "total", "points", "line_score"]:
        f = safe_float(obj.get(key) if isinstance(obj, dict) else None)
        if f is not None:
            return f
    return None

def clean_prop_rows(rows):
    out, seen = [], set()
    for r in rows or []:
        name = str(r.get("Player") or "").strip()
        market = r.get("Market")
        line = safe_float(r.get("Line"))
        if not name or not market or line is None:
            continue
        key = (normalize_name(name), market, line, r.get("Source"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

@st.cache_data(ttl=120, show_spinner=False)
def fetch_underdog_wnba_props():
    """Relationship-aware Underdog WNBA parser.

    v2.5 fix:
    Underdog separates the player, market, league, and line across related objects.
    The old parser saw payload_has_wnba=True but found OK_NO_WNBA_ROWS because
    no single flattened object had all fields. This version resolves relationships.
    """
    all_rows = []

    for url in UNDERDOG_URLS:
        data = safe_get_json(url, timeout=12)
        if not data:
            continue

        payload_text = json.dumps(data, default=str).lower()
        payload_has_wnba = ("wnba" in payload_text) or ("women" in payload_text) or ("women's" in payload_text)
        idx = build_underdog_id_index(data)
        objects = flatten_json(data)
        dynamic_wnba_names = extract_dynamic_wnba_names_from_payload(data)
        rows = []
        debug_candidates = 0
        debug_market = 0
        debug_name = 0
        debug_line = 0
        debug_rejected_name = 0

        for obj in objects:
            if not isinstance(obj, dict):
                continue

            combined = combine_obj_and_related_text(obj, idx, depth=2)
            combined_low = combined.lower()

            # Must pass WNBA/cross-sport protection.
            if not underdog_text_is_wnba(combined_low, payload_has_wnba=payload_has_wnba):
                continue
            debug_candidates += 1

            market = detect_market(combined)
            if market is None:
                continue
            debug_market += 1

            name = candidate_player_name_from_text_and_related(obj, idx)
            if not name:
                continue
            debug_name += 1

            raw_line = extract_underdog_line_from_obj_or_related(obj, idx, market=market, combined_text=combined)
            line = sane_wnba_line(market, raw_line)
            if line is None:
                continue
            debug_line += 1

            prop_date = parse_prop_date_from_text_or_obj(obj)
            price = -110
            a = ud_attrs(obj)
            for pk in ["american_price", "price", "odds"]:
                p = safe_float(a.get(pk))
                if p is not None and -10000 < p < 10000:
                    price = p
                    break

            # Final WNBA-only safety: reject non-player/event/team/NBA titles.
            if is_bad_player_like_name(name):
                debug_rejected_name += 1
                continue
            if not is_likely_wnba_name_dynamic(name, combined, dynamic_wnba_names):
                debug_rejected_name += 1
                continue

            rows.append({
                "Player": name,
                "Market": market,
                "Market Label": MARKET_LABELS.get(market, market),
                "Line": float(line),
                "Source": "Underdog",
                "Price": price,
                "Raw Market": combined[:180],
                "Real Line": True,
                "Prop Date": prop_date,
                "Game Day": day_label_from_date(prop_date),
                "Parser Mode": "relationship-aware-v2.5",
            })

        rows = clean_prop_rows(rows)

        # Debug sample: if we found names/lines but rejected all, show dynamic allowlist size and one sample.
        if not rows and (debug_market > 0 or debug_name > 0):
            try:
                sample_text = ""
                for obj2 in objects[:900]:
                    c2 = combine_obj_and_related_text(obj2, idx, depth=1)
                    nm2 = candidate_player_name_from_text_and_related(obj2, idx)
                    if detect_market(c2) and nm2:
                        sample_text = f"dynamic_names={len(dynamic_wnba_names)} | sample_name={nm2} | sample_text={c2[:420]}"
                        break
                if sample_text:
                    log_source_request(url, "DEBUG_REJECT_SAMPLE", sample_text)
            except Exception:
                pass

        if rows:
            all_rows.extend(rows)
            log_source_request(
                url,
                "OK",
                f"{len(rows)} WNBA props parsed relationship-aware | candidates={debug_candidates}, market={debug_market}, name={debug_name}, line={debug_line}, rejected_name={debug_rejected_name}, dynamic_names={len(dynamic_wnba_names)}, objects={len(objects)}"
            )
            break
        else:
            log_source_request(
                url,
                "OK_NO_WNBA_ROWS",
                f"payload_has_wnba={payload_has_wnba}, candidates={debug_candidates}, market={debug_market}, name={debug_name}, line={debug_line}, rejected_name={debug_rejected_name}, dynamic_names={len(dynamic_wnba_names)}, objects={len(objects)}"
            )

    return clean_prop_rows(all_rows)


@st.cache_data(ttl=180, show_spinner=False)
def fetch_prizepicks_wnba_props():
    data = safe_get_json(PRIZEPICKS_URL, timeout=8)
    if not data or not isinstance(data, dict):
        return []
    included = data.get("included", [])
    players = {}
    for x in included:
        if isinstance(x, dict):
            attrs = x.get("attributes", {}) or {}
            if x.get("type") in ["new_player", "player"]:
                players[str(x.get("id"))] = attrs.get("name") or attrs.get("display_name")
    rows = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {}) or {}
        rel = item.get("relationships", {}) or {}
        blob = json.dumps(item, default=str).lower()
        if "wnba" not in blob:
            continue
        market = detect_market(attrs.get("stat_type") or attrs.get("description") or blob)
        line = safe_float(attrs.get("line_score"))
        if market is None or line is None:
            continue
        player_name = attrs.get("name")
        if not player_name:
            try:
                player_id = rel.get("new_player", {}).get("data", {}).get("id")
                player_name = players.get(str(player_id))
            except Exception:
                pass
        if player_name:
            rows.append({
                "Player": player_name,
                "Market": market,
                "Market Label": MARKET_LABELS.get(market, market),
                "Line": line,
                "Source": "PrizePicks",
                "Price": -110,
                "Raw Market": str(attrs.get("stat_type", ""))[:140],
                "Real Line": True,
                "Prop Date": parse_prop_date_from_text_or_obj(item),
                "Game Day": day_label_from_date(parse_prop_date_from_text_or_obj(item)),
            })
    return clean_prop_rows(rows)

def fetch_all_real_wnba_props(source_choice):
    rows = []
    if source_choice in ["Underdog first", "Underdog only", "All available"]:
        rows.extend(fetch_underdog_wnba_props())
    if source_choice in ["PrizePicks backup only", "All available"] or (not rows and source_choice == "Underdog first"):
        rows.extend(fetch_prizepicks_wnba_props())
    return clean_prop_rows(rows)

# =========================
# LEARNING / CLV
# =========================
def player_market_key(player, market):
    return f"{normalize_name(player)}::{market}"

def apply_learning(player, market, proj):
    data = load_json(LEARN_FILE, {})
    rec = data.get(player_market_key(player, market), {})
    scale = safe_float(rec.get("scale"), 1.0) or 1.0
    samples = safe_int(rec.get("samples"), 0) or 0
    residual = safe_float(rec.get("avg_residual"), 0.0) or 0.0
    if samples < LEARNING_MIN_SAMPLES:
        return proj, scale, samples, "Learning warming up"
    return (proj * scale) + clamp(residual * 0.25, -1.25, 1.25), scale, samples, f"Learning x{scale:.3f}, residual {residual:+.2f}, n={samples}"

def update_learning(player, market, projected, actual):
    data = load_json(LEARN_FILE, {})
    key = player_market_key(player, market)
    rec = data.get(key, {"scale": 1.0, "samples": 0, "avg_residual": 0.0})
    projected, actual = safe_float(projected), safe_float(actual)
    if projected is None or projected <= 0 or actual is None:
        return rec
    old_scale = safe_float(rec.get("scale"), 1.0) or 1.0
    old_samples = safe_int(rec.get("samples"), 0) or 0
    old_resid = safe_float(rec.get("avg_residual"), 0.0) or 0.0
    err_pct = clamp((actual - projected) / max(projected, 1.0), -0.40, 0.40)
    resid = actual - projected
    rec.update({
        "scale": clamp(old_scale * (1 + LEARNING_RATE * err_pct), LEARNING_SCALE_MIN, LEARNING_SCALE_MAX),
        "samples": old_samples + 1,
        "avg_residual": round(((old_resid * old_samples) + resid) / max(old_samples + 1, 1), 3),
        "last_error_pct": round(err_pct, 4),
        "last_projected": projected,
        "last_actual": actual,
        "updated_at": now_iso(),
    })
    data[key] = rec
    save_json(LEARN_FILE, data)
    return rec

def update_clv_snapshot(player, market, source, line):
    if line is None:
        return 0.0
    data = load_json(CLV_FILE, {})
    key = f"{today_str()}::{normalize_name(player)}::{market}::{source}"
    line = float(line)
    old = data.get(key)
    if not old:
        data[key] = {"player": player, "market": market, "source": source, "open_line": line, "latest_line": line, "last_updated": now_iso()}
        save_json(CLV_FILE, data)
        return 0.0
    open_line = safe_float(old.get("open_line"), line)
    old["latest_line"] = line
    old["last_updated"] = now_iso()
    data[key] = old
    save_json(CLV_FILE, data)
    return round(line - open_line, 2)

def track_line_history(player, market, source, line):
    hist = load_json(LINE_HISTORY_FILE, {})
    key = f"{normalize_name(player)}::{market}::{source}"
    rows = hist.get(key, [])
    rows.append({"t": now_iso(), "line": safe_float(line)})
    hist[key] = rows[-40:]
    save_json(LINE_HISTORY_FILE, hist)
    if len(hist[key]) < 2:
        return 0.0
    first = safe_float(hist[key][0].get("line"))
    last = safe_float(hist[key][-1].get("line"))
    if first is None or last is None:
        return 0.0
    return round(last - first, 2)

# =========================
# PROJECTIONS
# =========================
def value_from_row(row, market):
    if not row:
        return None
    pts = safe_float(row.get("PTS"), 0) or 0
    reb = safe_float(row.get("REB"), 0) or 0
    ast = safe_float(row.get("AST"), 0) or 0
    stl = safe_float(row.get("STL"), 0) or 0
    blk = safe_float(row.get("BLK"), 0) or 0
    fg3m = safe_float(row.get("FG3M"), 0) or 0
    return {
        "points": pts,
        "rebounds": reb,
        "assists": ast,
        "pts_rebs_asts": pts + reb + ast,
        "pts_rebs": pts + reb,
        "pts_asts": pts + ast,
        "rebs_asts": reb + ast,
        "threes": fg3m,
        "steals": stl,
        "blocks": blk,
    }.get(market)

def project_market(prop, season_df, last5_df, last10_df):
    player, market, line = prop["Player"], prop["Market"], safe_float(prop["Line"])
    season = lookup_player_stat(player, season_df)
    l5 = lookup_player_stat(player, last5_df)
    l10 = lookup_player_stat(player, last10_df)

    parts = []
    for row, w, label in [(l5, 0.45, "L5"), (l10, 0.30, "L10"), (season, 0.25, "Season")]:
        val = value_from_row(row, market)
        if val is not None:
            parts.append((val, w, label))

    notes = []
    if parts:
        total_w = sum(w for _, w, _ in parts)
        proj = sum(v * w for v, w, _ in parts) / total_w
        score = 76 + min(18, len(parts) * 6)
        notes.append("Projection blend: " + ", ".join(label for _, _, label in parts))
        if season:
            min_val = safe_float(season.get("MIN"))
            if min_val is not None:
                notes.append(f"Season minutes {min_val:.1f}")
    else:
        # Not a fake line: real line anchor only when stats endpoint is blocked.
        proj = line if line is not None else 0.0
        score = 42
        notes.append("Stats endpoint unavailable/no match; projection anchored to real line with low confidence")

    if line is not None:
        gap = abs(proj - line)
        if gap > max(2.5, 0.27 * max(line, 1.0)):
            proj = (proj * 0.72) + (line * 0.28)
            score -= 6
            notes.append("Large projection/line gap; conservative blend toward market")

    proj, scale, samples, learn_note = apply_learning(player, market, proj)
    notes.append(learn_note)

    std_map = {
        "points": 5.5, "rebounds": 3.2, "assists": 2.8, "pts_rebs_asts": 7.4,
        "pts_rebs": 6.6, "pts_asts": 6.4, "rebs_asts": 4.4,
        "threes": 1.55, "steals": 1.05, "blocks": 0.95,
    }
    std = std_map.get(market, 4.5)
    if score < 60:
        std *= 1.25
    return float(max(0, proj)), float(std), int(clamp(score, 0, 100)), "; ".join(notes)

def classify_signal(proj, line, prob, ev, score):
    edge = abs(proj - line) if line is not None else 0
    notes = []
    if score < 55:
        notes.append("Low stat confidence")
    if edge < 0.35:
        notes.append("Projection too close to line")
    if prob is None or prob < 0.54:
        notes.append("Weak fair probability")

    if score >= MIN_ELITE_SCORE and prob is not None and prob >= MIN_ELITE_PROB and edge >= MIN_ELITE_EDGE and ev is not None and ev > 0:
        return "ELITE WATCH", notes or ["All strict gates passed"]
    if score >= MIN_PASS_SCORE and prob is not None and prob >= MIN_PASS_PROB and edge >= MIN_PASS_EDGE and ev is not None and ev > 0:
        return "PASS", notes or ["Bettable gates passed"]
    if score >= 62 and prob is not None and prob >= 0.54 and edge >= 0.35:
        return "LEAN", notes or ["Some gates passed"]
    return "NO BET", notes or ["Protection gates did not pass"]

def build_board(prop_rows, season_df, last5_df, last10_df):
    board = []
    for r in prop_rows:
        line = safe_float(r.get("Line"))
        if line is None:
            continue
        proj, std, score, proj_notes = project_market(r, season_df, last5_df, last10_df)
        side = "OVER" if proj > line else "UNDER"
        prob = normal_side_probability(proj, line, std, side)
        price = safe_float(r.get("Price"), -110) or -110
        ev = expected_value(prob, price)
        kelly = min(kelly_fraction(prob, price), MAX_RECOMMENDED_KELLY)
        signal, risk_notes = classify_signal(proj, line, prob, ev, score)
        board.append({
            "Player": r["Player"],
            "Market": r["Market"],
            "Market Label": r.get("Market Label", MARKET_LABELS.get(r["Market"], r["Market"])),
            "Game Day": r.get("Game Day", "Unknown"),
            "Prop Date": r.get("Prop Date"),
            "Line": line,
            "Projection": round(proj, 2),
            "Edge": round(proj - line, 2),
            "Abs Edge": round(abs(proj - line), 2),
            "Pick": side,
            "Fair Prob": round(prob * 100, 1) if prob is not None else None,
            "EV": round(ev * 100, 1) if ev is not None else None,
            "Kelly": round(kelly * 100, 2),
            "Data Score": score,
            "Signal": signal,
            "Source": r.get("Source"),
            "Price": price,
            "CLV Δ": update_clv_snapshot(r["Player"], r["Market"], r.get("Source"), line),
            "Line Δ": track_line_history(r["Player"], r["Market"], r.get("Source"), line),
            "Risk Notes": "; ".join(risk_notes),
            "Projection Notes": proj_notes,
            "Saved At": now_iso(),
            "App Version": APP_VERSION,
        })
    df = pd.DataFrame(board)
    if not df.empty:
        ranks = {"ELITE WATCH": 0, "PASS": 1, "LEAN": 2, "NO BET": 3}
        df["_rank"] = df["Signal"].map(ranks).fillna(9)
        df = df.sort_values(["_rank", "Data Score", "Abs Edge"], ascending=[True, False, False]).drop(columns=["_rank"])
    return df

# =========================
# SAVE / GRADE
# =========================
def save_official_snapshots(rows, tag="before"):
    existing = load_json(PICK_LOG, [])
    ba = load_json(BEFORE_AFTER_FILE, [])
    count = 0
    for row in rows or []:
        rec = dict(row)
        rec["Snapshot Type"] = tag
        rec["Snapshot Date"] = today_str()
        rec["Official ID"] = f"{today_str()}::{normalize_name(rec.get('Player'))}::{rec.get('Market')}::{rec.get('Source')}::{rec.get('Line')}::{tag}"
        if not any(x.get("Official ID") == rec["Official ID"] for x in existing):
            existing.append(rec)
            count += 1
        ba.append(rec)
    save_json(PICK_LOG, existing[-30000:])
    save_json(BEFORE_AFTER_FILE, ba[-40000:])
    return count

def grade_pick(row, actual):
    actual, line, pick = safe_float(actual), safe_float(row.get("Line")), row.get("Pick")
    if actual is None or line is None or pick not in ["OVER", "UNDER"]:
        return None
    if pick == "OVER":
        return "WIN" if actual > line else "LOSS" if actual < line else "PUSH"
    return "WIN" if actual < line else "LOSS" if actual > line else "PUSH"

def save_grade(player, market, line, actual, source_filter=None):
    picks = load_json(PICK_LOG, [])
    results = load_json(RESULT_LOG, [])
    matches = []
    for r in reversed(picks):
        if normalize_name(r.get("Player")) == normalize_name(player) and r.get("Market") == market and safe_float(r.get("Line")) == safe_float(line):
            if source_filter and r.get("Source") != source_filter:
                continue
            matches.append(r)
    count = 0
    for r in matches[:6]:
        result = grade_pick(r, actual)
        if result is None:
            continue
        out = dict(r)
        out.update({"Actual": safe_float(actual), "Graded Result": result, "Graded At": now_iso()})
        results.append(out)
        update_learning(out.get("Player"), out.get("Market"), out.get("Projection"), actual)
        count += 1
    save_json(RESULT_LOG, results[-30000:])
    return count

# =========================
# UI RENDER
# =========================
def render_games(games, label):
    if not games:
        st.info(f"No {label.lower()} games loaded. The app still works from real prop lines.")
        return
    for g in games:
        st.markdown(f"""
        <div class="game-card">
            <b>{g.get('Away')} @ {g.get('Home')}</b><br>
            <span class="small-muted">{g.get('Date')} • {g.get('Status')} • {g.get('Time')}</span>
        </div>
        """, unsafe_allow_html=True)

def render_player_cards(df, max_cards=200):
    if df.empty:
        st.info("No props match your filters.")
        return
    for _, row in df.head(max_cards).iterrows():
        sig = row["Signal"]
        card = "green-card" if sig in ["ELITE WATCH", "PASS"] else "warn-card" if sig == "LEAN" else "clean-card"
        badge = "good-badge" if sig in ["ELITE WATCH", "PASS"] else "yellow-badge" if sig == "LEAN" else "red-badge"
        st.markdown(f"""
        <div class="{card}">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                <div>
                    <div style="font-size:23px;font-weight:950;">{row['Player']}</div>
                    <div class="small-muted">{row.get('Game Day', 'Unknown')} • {row['Market Label']} • {row['Source']} • Price {row['Price']}</div>
                </div>
                <div><span class="badge {badge}">{sig}</span></div>
            </div>
            <div class="kpi-strip">
                <div class="kpi-box"><div class="kpi-label">Projection</div><div class="kpi-value">{row['Projection']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Line</div><div class="kpi-value">{row['Line']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Edge</div><div class="kpi-value">{row['Edge']:+.2f}</div></div>
                <div class="kpi-box"><div class="kpi-label">Pick</div><div class="kpi-value">{row['Pick']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Fair Prob</div><div class="kpi-value">{row['Fair Prob']}%</div><div class="kpi-sub">EV {row['EV']}%</div></div>
                <div class="kpi-box"><div class="kpi-label">Data Score</div><div class="kpi-value">{row['Data Score']}/100</div></div>
            </div>
            <div class="small-muted"><b>CLV Δ:</b> {row['CLV Δ']} • <b>Line Δ:</b> {row['Line Δ']} • <b>Kelly:</b> {row['Kelly']}%</div>
            <div class="small-muted"><b>Risk:</b> {row['Risk Notes']}</div>
            <div class="small-muted"><b>Model:</b> {row['Projection Notes']}</div>
        </div>
        """, unsafe_allow_html=True)

# =========================
# APP BODY
# =========================
st.markdown(f"""
<div class="hero-panel">
  <div class="big-title">🏀 WNBA Prop Engine</div>
  <div class="sub-title">Streamlit safe-load fix • Real lines only • Full player-card board • Before/After snapshots • Grading + learning</div>
  <span class="badge good-badge">{APP_VERSION}</span>
  <span class="badge blue-badge">Underdog first</span>
  <span class="badge">No fake lines</span>
  <span class="badge red-badge">WNBA-only sport filter</span>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Controls")
    source_choice = st.selectbox("Line source", ["Underdog first", "Underdog only", "PrizePicks backup only", "All available"], index=0)
    season = st.text_input("WNBA season", value=os.getenv("WNBA_SEASON", "2025"))
    load_stats = st.checkbox("Use WNBA stats endpoint for projections", value=False)
    selected_day = st.radio("Board filter", ["All Lines", "Today", "Tomorrow"], horizontal=True)
    st.divider()
    st.caption("Filters")
    selected_markets = st.multiselect("Markets", list(MARKET_LABELS.values()), default=list(MARKET_LABELS.values()))
    signal_filter = st.multiselect("Signals", ["ELITE WATCH", "PASS", "LEAN", "NO BET"], default=["ELITE WATCH", "PASS", "LEAN", "NO BET"])
    search_name = st.text_input("Optional player filter", value="")
    max_cards = st.slider("Max cards", 25, 300, 150)
    st.divider()
    save_tag = st.selectbox("Snapshot type", ["before", "after"], index=0)
    only_save = st.multiselect("Save only signals", ["ELITE WATCH", "PASS", "LEAN", "NO BET"], default=["ELITE WATCH", "PASS", "LEAN"])
    st.divider()
    refresh = st.button("🔄 Refresh / Load Board", use_container_width=True)

# Auto-load so the page is not blank.
if "loaded_once" not in st.session_state:
    st.session_state.loaded_once = True
    auto_load = True
else:
    auto_load = False

if refresh:
    st.cache_data.clear()

should_load = refresh or auto_load

if should_load:
    with st.spinner("Loading real WNBA prop board..."):
        prop_rows = fetch_all_real_wnba_props(source_choice)
        if load_stats:
            season_df = get_wnba_player_dashboard(season=season, last_n="0")
            last5_df = get_wnba_player_dashboard(season=season, last_n="5")
            last10_df = get_wnba_player_dashboard(season=season, last_n="10")
        else:
            season_df = pd.DataFrame()
            last5_df = pd.DataFrame()
            last10_df = pd.DataFrame()
        games_today = get_wnba_scoreboard(today_str())
        games_tomorrow = get_wnba_scoreboard(tomorrow_str())
        board_df = build_board(prop_rows, season_df, last5_df, last10_df)
        st.session_state["board_df"] = board_df
        st.session_state["games_today"] = games_today
        st.session_state["games_tomorrow"] = games_tomorrow
        st.session_state["stats_loaded"] = not season_df.empty

board_df = st.session_state.get("board_df", pd.DataFrame())
games_today = st.session_state.get("games_today", [])
games_tomorrow = st.session_state.get("games_tomorrow", [])
stats_loaded = st.session_state.get("stats_loaded", False)

if board_df.empty:
    st.markdown("""
    <div class="red-card">
    <b>No WNBA prop lines loaded yet.</b><br>
    Click Refresh / Load Board. If it still shows this, Underdog/PrizePicks did not return WNBA props or blocked the request.
    The app will not create fake lines. Keep Board filter = All Lines. If logs show market/name positive but line=0, use v2.6+ because Underdog moved lines into text/related fields.
    </div>
    """, unsafe_allow_html=True)
else:
    filt = board_df.copy()

    # Day filter fix:
    # Keep All Lines as the default because some real prop sources do not expose a usable game date.
    # Today/Tomorrow only filters rows that have a matching Game Day; Unknown rows are still shown
    # so posted Underdog lines do not disappear just because the schedule endpoint timed out.
    if selected_day in ["Today", "Tomorrow"] and "Game Day" in filt.columns:
        known_match = filt[filt["Game Day"].astype(str) == selected_day]
        unknown_rows = filt[filt["Game Day"].astype(str).isin(["Unknown", "", "None", "nan"])]
        filt = pd.concat([known_match, unknown_rows], ignore_index=True)

    if selected_markets:
        filt = filt[filt["Market Label"].isin(selected_markets)]
    if signal_filter:
        filt = filt[filt["Signal"].isin(signal_filter)]
    if search_name.strip():
        filt = filt[filt["Player"].str.lower().str.contains(search_name.lower(), na=False)]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Props shown", len(filt))
    c2.metric("Board filter", selected_day)
    c3.metric("Elite", int((filt["Signal"] == "ELITE WATCH").sum()))
    c4.metric("Pass", int((filt["Signal"] == "PASS").sum()))
    c5.metric("Lean", int((filt["Signal"] == "LEAN").sum()))
    c6.metric("Stats loaded", "YES" if stats_loaded else "LOW")

    save_rows = filt[filt["Signal"].isin(only_save)].to_dict("records") if only_save else filt.to_dict("records")
    if st.button(f"💾 Save official {save_tag} snapshots", use_container_width=True):
        n = save_official_snapshots(save_rows, tag=save_tag)
        st.success(f"Saved {n} official {save_tag} snapshots.")

    tab_cards, tab_table, tab_games, tab_saved, tab_grade, tab_learning = st.tabs(["🃏 Player Cards", "📋 Prop Table", "📅 Today/Tomorrow", "💾 Saved/CLV", "✅ Grade", "🧠 Learning"])

    with tab_cards:
        render_player_cards(filt, max_cards=max_cards)

    with tab_table:
        cols = ["Player", "Game Day", "Prop Date", "Market Label", "Line", "Projection", "Edge", "Pick", "Fair Prob", "EV", "Kelly", "Data Score", "Signal", "Source", "CLV Δ", "Line Δ", "Risk Notes", "Projection Notes"]
        safe_cols = [c for c in cols if c in filt.columns]
        st.dataframe(filt[safe_cols], use_container_width=True, height=740)
        st.download_button("Download board CSV", filt[safe_cols].to_csv(index=False).encode("utf-8"), "wnba_board.csv", "text/csv")

    with tab_games:
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Today")
            render_games(games_today, "Today")
        with g2:
            st.subheader("Tomorrow")
            render_games(games_tomorrow, "Tomorrow")

    with tab_saved:
        saved = pd.DataFrame(load_json(PICK_LOG, []))
        clv = pd.DataFrame(load_json(CLV_FILE, {}).values())
        st.subheader("Official saved snapshots")
        if not saved.empty:
            st.dataframe(saved.tail(600), use_container_width=True, height=350)
        else:
            st.info("No saved snapshots yet.")
        st.subheader("CLV tracker")
        if not clv.empty:
            st.dataframe(clv.tail(600), use_container_width=True, height=300)
        else:
            st.info("No CLV rows yet.")

    with tab_grade:
        with st.form("grade_form"):
            g_player = st.text_input("Player name")
            inv_market = {v: k for k, v in MARKET_LABELS.items()}
            g_market_label = st.selectbox("Market", list(MARKET_LABELS.values()))
            g_line = st.number_input("Saved line", min_value=0.0, max_value=100.0, step=0.5)
            g_actual = st.number_input("Actual result", min_value=0.0, max_value=150.0, step=0.5)
            g_source = st.text_input("Source filter optional", value="")
            submitted = st.form_submit_button("Grade and update learning")
            if submitted:
                n = save_grade(g_player, inv_market[g_market_label], g_line, g_actual, g_source or None)
                if n:
                    st.success(f"Graded {n} saved snapshot(s).")
                else:
                    st.warning("No matching saved snapshot found.")
        results = pd.DataFrame(load_json(RESULT_LOG, []))
        if not results.empty:
            st.dataframe(results.tail(600), use_container_width=True, height=360)
        else:
            st.info("No graded results yet.")

    with tab_learning:
        learn = load_json(LEARN_FILE, {})
        if not learn:
            st.info("Learning file is empty until you grade results.")
        else:
            rows = []
            for k, v in learn.items():
                player, market = k.split("::", 1) if "::" in k else (k, "")
                rows.append({"Player": player, "Market": market, "Scale": v.get("scale"), "Samples": v.get("samples"), "Avg Residual": v.get("avg_residual"), "Updated": v.get("updated_at")})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=520)

with st.expander("Source request log"):
    req_rows = load_json(REQUEST_LOG_FILE, [])
    if isinstance(req_rows, list) and len(req_rows) > 0:
        req_df = pd.DataFrame(req_rows)
        if not req_df.empty:
            st.dataframe(req_df.tail(120), use_container_width=True)
        else:
            st.caption("No request issues logged.")
    else:
        st.caption("No request issues logged.")
