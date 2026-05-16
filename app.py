# -*- coding: utf-8 -*-
# ============================================================
# WNBA PROP ENGINE — v2 Railway/Streamlit Ready
# Real lines only. Underdog-first. No fake prop lines.
# Full player cards + Today/Tomorrow games + advanced protection layers.
# ============================================================

import os
import re
import json
import math
import time
import difflib
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_VERSION = "WNBA v2.0 ADVANCED CARDS + TODAY/TOMORROW"

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
TEAM_CACHE_FILE = os.path.join(STORAGE_DIR, "team_cache.json")

# =========================
# SOURCES
# =========================
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

# Optional API keys. Put these in Railway variables or Streamlit secrets.
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
SPORTSGAMEODDS_API_KEY = os.getenv("SPORTSGAMEODDS_API_KEY", "")
OPTICODDS_API_KEY = os.getenv("OPTICODDS_API_KEY", "")

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

TEAM_ALIASES = {
    "ATL": "Atlanta Dream",
    "CHI": "Chicago Sky",
    "CON": "Connecticut Sun",
    "DAL": "Dallas Wings",
    "GSV": "Golden State Valkyries",
    "IND": "Indiana Fever",
    "LAS": "Los Angeles Sparks",
    "LVA": "Las Vegas Aces",
    "MIN": "Minnesota Lynx",
    "NYL": "New York Liberty",
    "PHX": "Phoenix Mercury",
    "SEA": "Seattle Storm",
    "WAS": "Washington Mystics",
}

# =========================
# MODEL SETTINGS
# =========================
MIN_BETTABLE_SCORE = 82
MIN_PASS_PROB = 0.58
MIN_PASS_EDGE = 0.65
MIN_ELITE_SCORE = 90
MIN_ELITE_PROB = 0.63
MIN_ELITE_EDGE = 1.00
MAX_RECOMMENDED_KELLY = 0.02

LEARNING_MIN_SAMPLES = 4
LEARNING_RATE = 0.045
LEARNING_SCALE_MIN = 0.90
LEARNING_SCALE_MAX = 1.10

DEFAULT_MINUTES = 24.0
DEFAULT_PACE = 80.0
SIMS = 9000

# =========================
# UI
# =========================
st.set_page_config(
    page_title="WNBA Prop Engine v2 — Real Lines",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top left,#141827 0%,#07090f 42%,#020204 100%);
    color:#fff;
}
.block-container {padding-top:1.0rem; max-width:1650px;}
h1,h2,h3 {color:#fff;}
.hero-panel {
    background:linear-gradient(135deg,rgba(30,38,72,.96),rgba(8,10,18,.98));
    border:1px solid rgba(128,162,255,.38);
    border-radius:26px;
    padding:22px;
    box-shadow:0 0 32px rgba(80,120,255,.16);
    margin-bottom:18px;
}
.clean-card {
    background:linear-gradient(145deg,#10131d,#090b12);
    border:1px solid rgba(145,170,255,.22);
    border-radius:20px;
    padding:18px;
    box-shadow:0 0 18px rgba(80,120,255,.08);
    margin-bottom:14px;
}
.green-card {
    background:linear-gradient(145deg,#061c13,#07100c);
    border:1px solid rgba(0,255,145,.34);
    border-radius:20px;
    padding:18px;
    box-shadow:0 0 20px rgba(0,255,145,.13);
    margin-bottom:14px;
}
.warn-card {
    background:linear-gradient(145deg,#211600,#100b02);
    border:1px solid rgba(255,195,70,.34);
    border-radius:20px;
    padding:18px;
    box-shadow:0 0 18px rgba(255,195,70,.10);
    margin-bottom:14px;
}
.red-card {
    background:linear-gradient(145deg,#240808,#100404);
    border:1px solid rgba(255,90,90,.34);
    border-radius:20px;
    padding:18px;
    box-shadow:0 0 18px rgba(255,90,90,.10);
    margin-bottom:14px;
}
.game-card {
    background:linear-gradient(145deg,#12182a,#080a12);
    border:1px solid rgba(145,170,255,.28);
    border-radius:18px;
    padding:14px;
    margin-bottom:10px;
}
.big-title {font-size:42px; font-weight:950; letter-spacing:-1px;}
.sub-title {color:#c7cfdf; font-size:15px; margin-top:-6px;}
.small-muted {color:#aeb6c8; font-size:13px;}
.badge {
    display:inline-block;
    padding:6px 11px;
    border-radius:999px;
    background:#141827;
    border:1px solid rgba(160,180,255,.38);
    color:#dce5ff;
    font-weight:850;
    margin:3px 4px 3px 0;
}
.good-badge {background:#002818;border-color:rgba(0,255,145,.48);color:#b9ffdc;}
.yellow-badge {background:#2a1e00;border-color:rgba(255,210,70,.48);color:#ffe6a6;}
.red-badge {background:#2a0707;border-color:rgba(255,90,90,.48);color:#ffc4c4;}
.blue-badge {background:#111d38;border-color:rgba(128,162,255,.48);color:#dce5ff;}
.kpi-strip {display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap:12px; margin:12px 0 18px 0;}
.kpi-box {background:linear-gradient(145deg,#10131d,#080a10);border:1px solid rgba(145,170,255,.24);border-radius:18px;padding:14px;min-height:92px;}
.kpi-label {font-size:12px;color:#aeb6c8;font-weight:850;letter-spacing:.04em;text-transform:uppercase;}
.kpi-value {font-size:25px;font-weight:950;color:#fff;margin-top:6px;}
.kpi-sub {font-size:12px;color:#c7cfdf;margin-top:5px;}
.stTabs [data-baseweb="tab"] {color:#b8c3cf;font-weight:850;}
.stTabs [aria-selected="true"] {color:#8db3ff!important;border-bottom:3px solid #8db3ff;}
[data-testid="stMetric"] {
    background:linear-gradient(145deg,#10131d,#080a10);
    border:1px solid rgba(145,170,255,.24);
    border-radius:18px;
    padding:13px;
}
@media (max-width: 1100px) {.kpi-strip {grid-template-columns: repeat(2, minmax(0, 1fr));}}
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
    rows.append({
        "time": now_iso(),
        "source": str(source)[:220],
        "status": str(status)[:80],
        "message": str(message)[:500],
    })
    save_json(REQUEST_LOG_FILE, rows[-500:])

def strip_accents(text):
    try:
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", str(text or ""))
            if not unicodedata.combining(ch)
        )
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

def safe_get_json(url, params=None, timeout=15, headers=None):
    try:
        h = {
            "User-Agent": "Mozilla/5.0 WNBAPropEngine/2.0",
            "Accept": "application/json,text/plain,*/*",
        }
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

def detect_team_text(text):
    blob = str(text or "").lower()
    for abbr, name in TEAM_ALIASES.items():
        if abbr.lower() in blob or name.lower() in blob:
            return abbr
    return None

# =========================
# BETTING MATH
# =========================
def decimal_odds(odds):
    odds = safe_float(odds)
    if odds is None:
        return None
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

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
    if side == "OVER":
        return float(clamp(1 - cdf, 0.001, 0.999))
    return float(clamp(cdf, 0.001, 0.999))

# =========================
# NBA/WNBA STATS
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
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=20)
    return stats_df_from_result(data)

@st.cache_data(ttl=1800, show_spinner=False)
def get_wnba_team_dashboard(season="2025"):
    url = f"{NBA_STATS_BASE}/leaguedashteamstats"
    params = {
        "Conference": "", "DateFrom": "", "DateTo": "", "Division": "", "GameScope": "",
        "GameSegment": "", "LastNGames": "0", "LeagueID": WNBA_LEAGUE_ID, "Location": "",
        "MeasureType": "Base", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
        "PORound": "0", "PaceAdjust": "N", "PerMode": "PerGame", "Period": "0",
        "PlusMinus": "N", "Rank": "N", "Season": season, "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "", "StarterBench": "",
        "TeamID": "0", "TwoWay": "0", "VsConference": "", "VsDivision": "",
    }
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=20)
    return stats_df_from_result(data)

@st.cache_data(ttl=1800, show_spinner=False)
def get_wnba_team_opponent_dashboard(season="2025"):
    url = f"{NBA_STATS_BASE}/leaguedashteamstats"
    params = {
        "Conference": "", "DateFrom": "", "DateTo": "", "Division": "", "GameScope": "",
        "GameSegment": "", "LastNGames": "0", "LeagueID": WNBA_LEAGUE_ID, "Location": "",
        "MeasureType": "Opponent", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
        "PORound": "0", "PaceAdjust": "N", "PerMode": "PerGame", "Period": "0",
        "PlusMinus": "N", "Rank": "N", "Season": season, "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "", "StarterBench": "",
        "TeamID": "0", "TwoWay": "0", "VsConference": "", "VsDivision": "",
    }
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=20)
    return stats_df_from_result(data)

@st.cache_data(ttl=900, show_spinner=False)
def get_wnba_scoreboard(date_str):
    url = f"{NBA_STATS_BASE}/scoreboardv2"
    params = {
        "DayOffset": "0",
        "GameDate": date_str,
        "LeagueID": WNBA_LEAGUE_ID,
    }
    data = safe_get_json(url, params=params, headers=nba_stats_headers(), timeout=20)
    games = stats_df_from_result(data, 0)
    linescore = stats_df_from_result(data, 1)
    out = []
    if games.empty:
        return out

    for _, g in games.iterrows():
        gid = str(g.get("GAME_ID", ""))
        home_id = g.get("HOME_TEAM_ID")
        away_id = g.get("VISITOR_TEAM_ID")
        status = g.get("GAME_STATUS_TEXT", "")
        game_time = g.get("GAME_DATE_EST") or date_str

        home_name = ""
        away_name = ""
        try:
            sub = linescore[linescore["GAME_ID"].astype(str) == gid]
            for _, lr in sub.iterrows():
                tid = lr.get("TEAM_ID")
                name = lr.get("TEAM_NAME") or lr.get("TEAM_CITY_NAME") or ""
                abbr = lr.get("TEAM_ABBREVIATION") or ""
                if str(tid) == str(home_id):
                    home_name = abbr or name
                if str(tid) == str(away_id):
                    away_name = abbr or name
        except Exception:
            pass

        out.append({
            "Game ID": gid,
            "Date": date_str,
            "Away": away_name or str(away_id),
            "Home": home_name or str(home_id),
            "Status": status,
            "Time": str(game_time),
        })
    return out

def lookup_player_stat(player_name, stats_df):
    if stats_df is None or stats_df.empty or not player_name:
        return None
    best = None
    best_score = 0
    for _, r in stats_df.iterrows():
        nm = str(r.get("PLAYER_NAME", ""))
        sc = name_score(player_name, nm)
        if sc > best_score:
            best_score = sc
            best = r
    if best is None or best_score < 0.78:
        return None
    d = best.to_dict()
    d["_name_match_score"] = round(best_score, 3)
    return d

def team_row(team_abbr_or_name, team_df):
    if team_df is None or team_df.empty or not team_abbr_or_name:
        return None
    query = str(team_abbr_or_name)
    best = None
    best_score = 0
    for _, r in team_df.iterrows():
        nm = str(r.get("TEAM_NAME", ""))
        abbr = str(r.get("TEAM_ABBREVIATION", ""))
        sc = max(name_score(query, nm), name_score(query, abbr))
        if sc > best_score:
            best_score = sc
            best = r
    if best is None or best_score < 0.65:
        return None
    return best.to_dict()

# =========================
# REAL PROPS PARSING
# =========================
def detect_market(text):
    t = str(text or "").lower()
    t = t.replace("-", " ").replace("_", " ")
    t = " ".join(t.split())
    if "fantasy" in t:
        return None
    for key, aliases in SUPPORTED_MARKETS.items():
        for alias in aliases:
            a = alias.lower().replace("-", " ")
            if a in t:
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
        v = obj.get(key) if isinstance(obj, dict) else None
        f = safe_float(v)
        if f is not None:
            return f
    return None

def clean_prop_rows(rows):
    out = []
    seen = set()
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
    all_rows = []
    for url in UNDERDOG_URLS:
        data = safe_get_json(url, timeout=18)
        if not data:
            continue

        objects = flatten_json(data)
        for obj in objects:
            if not isinstance(obj, dict):
                continue

            text_blob = json.dumps(obj, default=str).lower()
            if "wnba" not in text_blob and "women" not in text_blob:
                continue

            market_text = " ".join(str(obj.get(k, "")) for k in [
                "over_under", "over_under_title", "stat_type", "stat", "title",
                "appearance_stat", "display_stat", "option_display"
            ])
            market = detect_market(market_text) or detect_market(text_blob)
            if market is None:
                continue

            name = None
            for k in ["player_name", "athlete_name", "title", "name", "full_name"]:
                val = obj.get(k)
                if isinstance(val, str) and len(val.split()) >= 2 and not detect_market(val):
                    name = val
                    break

            if not name:
                for k in ["player", "athlete", "appearance"]:
                    nested = obj.get(k)
                    if isinstance(nested, dict):
                        for nk in ["name", "full_name", "display_name", "player_name"]:
                            val = nested.get(nk)
                            if isinstance(val, str) and len(val.split()) >= 2:
                                name = val
                                break
                    if name:
                        break

            line = extract_number_line(obj)
            if not name or line is None:
                continue

            team = None
            opp = None
            for tk in ["team", "team_abbreviation", "team_name"]:
                tv = obj.get(tk)
                if isinstance(tv, str):
                    team = detect_team_text(tv) or tv
            team = team or detect_team_text(text_blob)

            price = safe_float(obj.get("american_price"), None)
            all_rows.append({
                "Player": name,
                "Market": market,
                "Market Label": MARKET_LABELS.get(market, market),
                "Line": line,
                "Source": "Underdog",
                "Price": price if price is not None else -110,
                "Raw Market": market_text[:140],
                "Team": team,
                "Opponent": opp,
                "Book Count": 1,
                "Alt Line": False,
                "Real Line": True,
            })

        if all_rows:
            log_source_request(url, "OK", f"{len(all_rows)} WNBA props parsed")
            break

    return clean_prop_rows(all_rows)

@st.cache_data(ttl=180, show_spinner=False)
def fetch_prizepicks_wnba_props():
    data = safe_get_json(PRIZEPICKS_URL, timeout=18)
    if not data:
        return []
    included = data.get("included", []) if isinstance(data, dict) else []
    players = {}
    for x in included:
        if not isinstance(x, dict):
            continue
        attrs = x.get("attributes", {}) or {}
        if x.get("type") in ["new_player", "player"]:
            players[str(x.get("id"))] = attrs.get("name") or attrs.get("display_name")

    rows = []
    for item in data.get("data", []) if isinstance(data, dict) else []:
        attrs = item.get("attributes", {}) or {}
        rel = item.get("relationships", {}) or {}
        blob = json.dumps(item, default=str).lower()
        if "wnba" not in blob:
            continue
        market = detect_market(attrs.get("stat_type") or attrs.get("description") or blob)
        if market is None:
            continue
        line = safe_float(attrs.get("line_score"))
        if line is None:
            continue
        player_name = attrs.get("name")
        if not player_name:
            player_id = None
            try:
                player_id = rel.get("new_player", {}).get("data", {}).get("id")
            except Exception:
                pass
            player_name = players.get(str(player_id))
        if not player_name:
            continue
        rows.append({
            "Player": player_name,
            "Market": market,
            "Market Label": MARKET_LABELS.get(market, market),
            "Line": line,
            "Source": "PrizePicks",
            "Price": -110,
            "Raw Market": str(attrs.get("stat_type", ""))[:140],
            "Team": detect_team_text(blob),
            "Opponent": None,
            "Book Count": 1,
            "Alt Line": False,
            "Real Line": True,
        })
    return clean_prop_rows(rows)

def merge_multi_book_lines(rows):
    """Group same player/market across books and mark consensus/alternate lines."""
    if not rows:
        return []
    grouped = {}
    for r in rows:
        key = (normalize_name(r["Player"]), r["Market"])
        grouped.setdefault(key, []).append(r)

    merged = []
    for _, group in grouped.items():
        lines = [safe_float(x.get("Line")) for x in group if safe_float(x.get("Line")) is not None]
        consensus = float(np.median(lines)) if lines else None
        unique_sources = sorted(set(str(x.get("Source")) for x in group))
        for r in group:
            rr = dict(r)
            rr["Consensus Line"] = consensus
            rr["Book Count"] = len(unique_sources)
            rr["Alt Line"] = consensus is not None and abs((safe_float(rr.get("Line")) or 0) - consensus) >= 1.0
            rr["Books"] = ", ".join(unique_sources)
            merged.append(rr)
    return merged

def fetch_all_real_wnba_props(source_choice):
    rows = []
    if source_choice in ["Underdog first", "Underdog only", "All available"]:
        rows.extend(fetch_underdog_wnba_props())
    if source_choice in ["PrizePicks backup only", "All available"] or (not rows and source_choice == "Underdog first"):
        rows.extend(fetch_prizepicks_wnba_props())
    return clean_prop_rows(merge_multi_book_lines(rows))

# =========================
# CONTEXT ENGINES
# =========================
def infer_player_team(player_row):
    if not player_row:
        return None
    return player_row.get("TEAM_ABBREVIATION") or player_row.get("TEAM_NAME")

def find_opponent_from_games(team, games):
    if not team or not games:
        return None
    team_norm = normalize_name(team)
    for g in games:
        home = str(g.get("Home", ""))
        away = str(g.get("Away", ""))
        if normalize_name(home) == team_norm or home.lower() == str(team).lower():
            return away
        if normalize_name(away) == team_norm or away.lower() == str(team).lower():
            return home
    return None

def lineup_confirmation_score(player_row, games_today, games_tomorrow, selected_day):
    """WNBA public confirmed starting lineups are not always available.
    This gate uses scheduled game presence + active stat match as a proxy.
    """
    if not player_row:
        return 35, "No stats match; lineup not confirmed"
    team = infer_player_team(player_row)
    games = games_today if selected_day == "Today" else games_tomorrow
    opp = find_opponent_from_games(team, games)
    gp = safe_float(player_row.get("GP"), 0) or 0
    minutes = safe_float(player_row.get("MIN"), 0) or 0

    score = 58
    notes = []
    if opp:
        score += 20
        notes.append(f"Team scheduled vs {opp}")
    else:
        notes.append("No matching scheduled game found")
    if minutes >= 28:
        score += 10
        notes.append("Core minutes role")
    elif minutes >= 20:
        score += 5
        notes.append("Rotation role")
    else:
        score -= 8
        notes.append("Low minute role")
    if gp >= 5:
        score += 6
    return int(clamp(score, 0, 100)), "; ".join(notes)

def rolling_usage_minutes(player, season_df, last5_df, last10_df):
    """Rolling usage/minutes engine using LastNGames endpoints when available."""
    season = lookup_player_stat(player, season_df)
    l5 = lookup_player_stat(player, last5_df)
    l10 = lookup_player_stat(player, last10_df)

    min_season = safe_float(season.get("MIN") if season else None)
    min5 = safe_float(l5.get("MIN") if l5 else None)
    min10 = safe_float(l10.get("MIN") if l10 else None)

    parts = []
    if min5 is not None:
        parts.append((min5, 0.50, "L5"))
    if min10 is not None:
        parts.append((min10, 0.30, "L10"))
    if min_season is not None:
        parts.append((min_season, 0.20, "Season"))
    if not parts:
        return DEFAULT_MINUTES, "Minutes fallback"

    total_w = sum(w for _, w, _ in parts)
    proj_min = sum(v * w for v, w, _ in parts) / total_w
    note = "Minutes blend: " + ", ".join(f"{src} {v:.1f}" for v, _, src in parts)
    return float(clamp(proj_min, 4, 40)), note

def rate_from_row(row, market, minutes):
    if not row:
        return None
    pts = safe_float(row.get("PTS"), 0) or 0
    reb = safe_float(row.get("REB"), 0) or 0
    ast = safe_float(row.get("AST"), 0) or 0
    stl = safe_float(row.get("STL"), 0) or 0
    blk = safe_float(row.get("BLK"), 0) or 0
    fg3m = safe_float(row.get("FG3M"), 0) or 0
    base_map = {
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
    }
    val = safe_float(base_map.get(market))
    min_played = safe_float(row.get("MIN"), minutes) or minutes
    if val is None or min_played <= 0:
        return None
    return val / min_played

def rolling_rate_projection(player, market, proj_minutes, season_df, last5_df, last10_df):
    season = lookup_player_stat(player, season_df)
    l5 = lookup_player_stat(player, last5_df)
    l10 = lookup_player_stat(player, last10_df)

    parts = []
    for row, w, label in [(l5, 0.45, "L5"), (l10, 0.30, "L10"), (season, 0.25, "Season")]:
        rate = rate_from_row(row, market, proj_minutes)
        if rate is not None:
            parts.append((rate, w, label))
    if not parts:
        return None, "No rolling rate data"
    total_w = sum(w for _, w, _ in parts)
    blended_rate = sum(r * w for r, w, _ in parts) / total_w
    proj = blended_rate * proj_minutes
    note = "Rate blend: " + ", ".join(f"{label}" for _, _, label in parts)
    return float(max(0, proj)), note

def opponent_defense_factor(market, opponent, opp_df):
    if not opponent or opp_df is None or opp_df.empty:
        return 1.0, "Opponent defense unavailable"
    row = team_row(opponent, opp_df)
    if not row:
        return 1.0, "Opponent defense no match"

    # Opponent dashboard columns vary. Use available allowed stats as broad defense proxy.
    col_map = {
        "points": "OPP_PTS",
        "rebounds": "OPP_REB",
        "assists": "OPP_AST",
        "pts_rebs_asts": "OPP_PTS",
        "pts_rebs": "OPP_PTS",
        "pts_asts": "OPP_PTS",
        "rebs_asts": "OPP_REB",
        "threes": "OPP_FG3M",
        "steals": "OPP_TOV",
        "blocks": "OPP_BLK",
    }
    col = col_map.get(market)
    if col not in row:
        return 1.0, "Opponent defense column unavailable"

    val = safe_float(row.get(col))
    if val is None:
        return 1.0, "Opponent defense value unavailable"

    try:
        league_vals = pd.to_numeric(opp_df[col], errors="coerce").dropna()
        lg = float(league_vals.mean()) if len(league_vals) else val
    except Exception:
        lg = val

    if lg <= 0:
        return 1.0, "Opponent defense neutral"

    # If opponent allows more than league average, boost projection; less, cut projection.
    diff = (val - lg) / lg
    factor = clamp(1 + diff * 0.18, 0.94, 1.06)
    return factor, f"Opponent defense {opponent} {col} factor x{factor:.3f}"

def pace_factor(team, opponent, team_df):
    if team_df is None or team_df.empty:
        return 1.0, "Pace unavailable"
    team_r = team_row(team, team_df)
    opp_r = team_row(opponent, team_df)
    paces = []
    for r in [team_r, opp_r]:
        if r and "PACE" in r:
            p = safe_float(r.get("PACE"))
            if p:
                paces.append(p)
    if not paces:
        return 1.0, "Pace column unavailable"
    game_pace = float(np.mean(paces))
    try:
        lg = float(pd.to_numeric(team_df["PACE"], errors="coerce").dropna().mean())
    except Exception:
        lg = DEFAULT_PACE
    if not lg or math.isnan(lg):
        lg = DEFAULT_PACE
    factor = clamp(game_pace / lg, 0.94, 1.06)
    return factor, f"Pace factor x{factor:.3f} game pace {game_pace:.1f}"

def implied_total_factor(team, opponent):
    """Placeholder for real odds API keys. Neutral unless valid odds feed is added."""
    # Keep neutral. This prevents fake implied totals.
    return 1.0, "Implied totals unavailable; neutral"

def blowout_risk_factor(team, opponent, team_df):
    if team_df is None or team_df.empty or not team or not opponent:
        return 1.0, "Blowout risk unavailable"
    tr = team_row(team, team_df)
    orow = team_row(opponent, team_df)
    if not tr or not orow:
        return 1.0, "Blowout risk no team match"

    plus_cols = ["PLUS_MINUS", "PLUS_MINUS_RANK"]
    pm_t = safe_float(tr.get("PLUS_MINUS"))
    pm_o = safe_float(orow.get("PLUS_MINUS"))
    if pm_t is None or pm_o is None:
        return 1.0, "Blowout risk neutral"
    spread_proxy = abs(pm_t - pm_o)
    if spread_proxy >= 10:
        return 0.965, f"High blowout risk proxy {spread_proxy:.1f}; minutes haircut"
    if spread_proxy >= 7:
        return 0.980, f"Moderate blowout risk proxy {spread_proxy:.1f}"
    return 1.0, f"Low blowout risk proxy {spread_proxy:.1f}"

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
    adjusted = (proj * scale) + clamp(residual * 0.25, -1.25, 1.25)
    return adjusted, scale, samples, f"Advanced learning x{scale:.3f}, residual {residual:+.2f}, n={samples}"

def update_learning(player, market, projected, actual):
    data = load_json(LEARN_FILE, {})
    key = player_market_key(player, market)
    rec = data.get(key, {"scale": 1.0, "samples": 0, "avg_residual": 0.0, "wins": 0, "losses": 0})
    projected = safe_float(projected)
    actual = safe_float(actual)
    if projected is None or projected <= 0 or actual is None:
        return rec

    old_scale = safe_float(rec.get("scale"), 1.0) or 1.0
    old_samples = safe_int(rec.get("samples"), 0) or 0
    old_resid = safe_float(rec.get("avg_residual"), 0.0) or 0.0
    err_pct = clamp((actual - projected) / max(projected, 1.0), -0.40, 0.40)
    resid = actual - projected

    new_scale = clamp(old_scale * (1 + LEARNING_RATE * err_pct), LEARNING_SCALE_MIN, LEARNING_SCALE_MAX)
    new_resid = ((old_resid * old_samples) + resid) / max(old_samples + 1, 1)

    rec.update({
        "scale": new_scale,
        "samples": old_samples + 1,
        "avg_residual": round(new_resid, 3),
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
        data[key] = {
            "player": player, "market": market, "source": source,
            "open_line": line, "latest_line": line, "last_updated": now_iso(),
        }
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
def fallback_projection_from_line(line):
    line = safe_float(line, 0.0) or 0.0
    return line, "Fallback projection anchored to real line; low confidence"

def market_std(market, data_score):
    std_map = {
        "points": 5.5, "rebounds": 3.2, "assists": 2.8,
        "pts_rebs_asts": 7.4, "pts_rebs": 6.6, "pts_asts": 6.4,
        "rebs_asts": 4.4, "threes": 1.55, "steals": 1.05, "blocks": 0.95,
    }
    std = std_map.get(market, 4.5)
    if data_score < 60:
        std *= 1.25
    return std

def project_market(prop, season_df, last5_df, last10_df, team_df, opp_df, games_today, games_tomorrow, selected_day):
    player = prop["Player"]
    market = prop["Market"]
    line = safe_float(prop["Line"])
    source = prop.get("Source", "Unknown")

    season_row = lookup_player_stat(player, season_df)
    data_score = 40
    notes = []

    team = prop.get("Team") or infer_player_team(season_row)
    games_for_day = games_today if selected_day == "Today" else games_tomorrow
    opponent = prop.get("Opponent") or find_opponent_from_games(team, games_for_day)

    if season_row:
        data_score = 72
        notes.append("WNBA season stat match")
        if season_row.get("_name_match_score", 0) >= 0.90:
            data_score += 4
    else:
        notes.append("No season stat match")

    lineup_score, lineup_note = lineup_confirmation_score(season_row, games_today, games_tomorrow, selected_day)
    data_score += int((lineup_score - 50) * 0.25)
    notes.append(lineup_note)

    proj_minutes, minutes_note = rolling_usage_minutes(player, season_df, last5_df, last10_df)
    notes.append(minutes_note)

    proj, rate_note = rolling_rate_projection(player, market, proj_minutes, season_df, last5_df, last10_df)
    if proj is None:
        proj, fb_note = fallback_projection_from_line(line)
        notes.append(fb_note)
        data_score = min(data_score, 45)
    else:
        notes.append(rate_note)
        data_score += 8

    opp_factor, opp_note = opponent_defense_factor(market, opponent, opp_df)
    pace_adj, pace_note = pace_factor(team, opponent, team_df)
    total_factor, total_note = implied_total_factor(team, opponent)
    blow_factor, blow_note = blowout_risk_factor(team, opponent, team_df)

    for factor, note in [(opp_factor, opp_note), (pace_adj, pace_note), (total_factor, total_note), (blow_factor, blow_note)]:
        proj *= factor
        notes.append(note)

    if prop.get("Alt Line"):
        data_score -= 5
        notes.append("Alternate/non-consensus line flagged")

    # Market sanity blend: protect against stale stats by blending toward real line if projection is too far.
    if line is not None:
        gap = abs(proj - line)
        if gap > max(2.5, 0.27 * max(line, 1.0)):
            proj = (proj * 0.72) + (line * 0.28)
            data_score -= 6
            notes.append("Large projection/line gap; conservative blend toward real line")

    proj, scale, samples, learn_note = apply_learning(player, market, proj)
    notes.append(learn_note)

    std = market_std(market, data_score)
    return {
        "projection": float(max(0, proj)),
        "std": float(std),
        "data_score": int(clamp(data_score, 0, 100)),
        "notes": "; ".join(notes),
        "team": team,
        "opponent": opponent,
        "projected_minutes": round(proj_minutes, 1),
        "lineup_score": lineup_score,
    }

def classify_signal(proj, line, prob, ev, data_score, source, lineup_score, book_count, alt_line):
    if line is None:
        return "NO LINE", "red", ["No real line available"]
    edge = abs(proj - line)
    notes = []

    if data_score < 55:
        notes.append("Low stat-data confidence")
    if lineup_score < 65:
        notes.append("Lineup/game confirmation weak")
    if book_count < 2:
        notes.append("Single-book line")
    if alt_line:
        notes.append("Alternate-line flag")
    if edge < 0.35:
        notes.append("Projection too close to line")
    if prob is None or prob < 0.54:
        notes.append("Weak fair probability")

    if data_score >= MIN_ELITE_SCORE and lineup_score >= 72 and prob >= MIN_ELITE_PROB and edge >= MIN_ELITE_EDGE and ev is not None and ev > 0:
        return "ELITE WATCH", "green", notes or ["All strict gates passed"]
    if data_score >= MIN_BETTABLE_SCORE and lineup_score >= 65 and prob >= MIN_PASS_PROB and edge >= MIN_PASS_EDGE and ev is not None and ev > 0:
        return "PASS", "green", notes or ["Bettable gates passed"]
    if data_score >= 64 and prob >= 0.54 and edge >= 0.35:
        return "LEAN", "yellow", notes or ["Some gates passed, not strong enough"]
    return "NO BET", "red", notes or ["Protection gates did not pass"]

def build_board(prop_rows, season_df, last5_df, last10_df, team_df, opp_df, games_today, games_tomorrow, selected_day):
    board = []
    for r in prop_rows:
        line = safe_float(r.get("Line"))
        if line is None:
            continue

        ctx = project_market(r, season_df, last5_df, last10_df, team_df, opp_df, games_today, games_tomorrow, selected_day)
        proj = ctx["projection"]
        std = ctx["std"]
        price = safe_float(r.get("Price"), -110) or -110
        side = "OVER" if proj > line else "UNDER"
        prob = normal_side_probability(proj, line, std, side)
        ev = expected_value(prob, price)
        kelly = min(kelly_fraction(prob, price), MAX_RECOMMENDED_KELLY)
        clv_delta = update_clv_snapshot(r["Player"], r["Market"], r.get("Source"), line)
        line_delta = track_line_history(r["Player"], r["Market"], r.get("Source"), line)

        signal, color, risk_notes = classify_signal(
            proj, line, prob, ev, ctx["data_score"], r.get("Source"),
            ctx["lineup_score"], safe_int(r.get("Book Count"), 1) or 1, bool(r.get("Alt Line")),
        )

        board.append({
            "Player": r["Player"],
            "Team": ctx["team"],
            "Opponent": ctx["opponent"],
            "Game Day": selected_day,
            "Market": r["Market"],
            "Market Label": r.get("Market Label", MARKET_LABELS.get(r["Market"], r["Market"])),
            "Line": line,
            "Consensus Line": r.get("Consensus Line", line),
            "Projection": round(proj, 2),
            "Projected Minutes": ctx["projected_minutes"],
            "Edge": round(proj - line, 2),
            "Abs Edge": round(abs(proj - line), 2),
            "Pick": side,
            "Fair Prob": round(prob * 100, 1) if prob is not None else None,
            "EV": round(ev * 100, 1) if ev is not None else None,
            "Kelly": round(kelly * 100, 2),
            "Data Score": ctx["data_score"],
            "Lineup Score": ctx["lineup_score"],
            "Signal": signal,
            "Source": r.get("Source"),
            "Books": r.get("Books", r.get("Source")),
            "Book Count": r.get("Book Count", 1),
            "Alt Line": bool(r.get("Alt Line")),
            "Price": price,
            "CLV Δ": clv_delta,
            "Line Δ": line_delta,
            "Risk Notes": "; ".join(risk_notes),
            "Projection Notes": ctx["notes"],
            "Saved At": now_iso(),
            "App Version": APP_VERSION,
        })

    df = pd.DataFrame(board)
    if not df.empty:
        sig_rank = {"ELITE WATCH": 0, "PASS": 1, "LEAN": 2, "NO BET": 3, "NO LINE": 4}
        df["_rank"] = df["Signal"].map(sig_rank).fillna(9)
        df = df.sort_values(["_rank", "Data Score", "Lineup Score", "Abs Edge"], ascending=[True, False, False, False]).drop(columns=["_rank"])
    return df

# =========================
# SAVE / GRADE
# =========================
def save_official_snapshots(rows, tag="before"):
    if rows is None or len(rows) == 0:
        return 0
    existing = load_json(PICK_LOG, [])
    ba = load_json(BEFORE_AFTER_FILE, [])
    today = today_str()
    count = 0

    for row in rows:
        rec = dict(row)
        rec["Snapshot Type"] = tag
        rec["Snapshot Date"] = today
        rec["Official ID"] = f"{today}::{normalize_name(rec.get('Player'))}::{rec.get('Market')}::{rec.get('Source')}::{rec.get('Line')}::{tag}"
        if not any(x.get("Official ID") == rec["Official ID"] for x in existing):
            existing.append(rec)
            count += 1
        ba.append(rec)

    save_json(PICK_LOG, existing[-30000:])
    save_json(BEFORE_AFTER_FILE, ba[-40000:])
    return count

def grade_pick(row, actual):
    actual = safe_float(actual)
    line = safe_float(row.get("Line"))
    pick = row.get("Pick")
    if actual is None or line is None or pick not in ["OVER", "UNDER"]:
        return None
    if pick == "OVER":
        if actual > line:
            return "WIN"
        if actual < line:
            return "LOSS"
        return "PUSH"
    if actual < line:
        return "WIN"
    if actual > line:
        return "LOSS"
    return "PUSH"

def save_grade(player, market, line, actual, source_filter=None):
    picks = load_json(PICK_LOG, [])
    results = load_json(RESULT_LOG, [])
    matches = []
    for r in reversed(picks):
        if normalize_name(r.get("Player")) == normalize_name(player) and r.get("Market") == market:
            if source_filter and r.get("Source") != source_filter:
                continue
            if safe_float(r.get("Line")) == safe_float(line):
                matches.append(r)

    if not matches:
        return 0

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
# RENDER
# =========================
def render_games(games, label):
    if not games:
        st.info(f"No {label.lower()} WNBA games loaded from the stats endpoint.")
        return
    for g in games:
        st.markdown(f"""
        <div class="game-card">
            <b>{g.get('Away')} @ {g.get('Home')}</b><br>
            <span class="small-muted">{g.get('Date')} • {g.get('Status')} • {g.get('Time')}</span>
        </div>
        """, unsafe_allow_html=True)

def render_player_cards(df, max_cards=250):
    if df.empty:
        st.info("No props match the current filters.")
        return
    for _, row in df.head(max_cards).iterrows():
        sig = row["Signal"]
        card = "green-card" if sig in ["ELITE WATCH", "PASS"] else "warn-card" if sig == "LEAN" else "clean-card"
        badge = "good-badge" if sig in ["ELITE WATCH", "PASS"] else "yellow-badge" if sig == "LEAN" else "red-badge"
        alt_badge = '<span class="badge yellow-badge">ALT LINE</span>' if row.get("Alt Line") else ""
        st.markdown(f"""
        <div class="{card}">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                <div>
                    <div style="font-size:23px;font-weight:950;">{row['Player']}</div>
                    <div class="small-muted">{row['Team'] or 'Team N/A'} vs {row['Opponent'] or 'Opp N/A'} • {row['Market Label']} • {row['Source']}</div>
                </div>
                <div><span class="badge {badge}">{sig}</span>{alt_badge}</div>
            </div>
            <div class="kpi-strip">
                <div class="kpi-box"><div class="kpi-label">Projection</div><div class="kpi-value">{row['Projection']}</div><div class="kpi-sub">Min {row['Projected Minutes']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Line</div><div class="kpi-value">{row['Line']}</div><div class="kpi-sub">Consensus {row['Consensus Line']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Edge</div><div class="kpi-value">{row['Edge']:+.2f}</div></div>
                <div class="kpi-box"><div class="kpi-label">Pick</div><div class="kpi-value">{row['Pick']}</div></div>
                <div class="kpi-box"><div class="kpi-label">Fair Prob</div><div class="kpi-value">{row['Fair Prob']}%</div><div class="kpi-sub">EV {row['EV']}%</div></div>
                <div class="kpi-box"><div class="kpi-label">Scores</div><div class="kpi-value">{row['Data Score']}/100</div><div class="kpi-sub">Lineup {row['Lineup Score']}/100</div></div>
            </div>
            <div class="small-muted"><b>Books:</b> {row['Books']} • <b>CLV Δ:</b> {row['CLV Δ']} • <b>Line Δ:</b> {row['Line Δ']} • <b>Kelly:</b> {row['Kelly']}%</div>
            <div class="small-muted"><b>Risk:</b> {row['Risk Notes']}</div>
            <div class="small-muted"><b>Model:</b> {row['Projection Notes']}</div>
        </div>
        """, unsafe_allow_html=True)

# =========================
# APP
# =========================
st.markdown(f"""
<div class="hero-panel">
  <div class="big-title">🏀 WNBA Prop Engine</div>
  <div class="sub-title">Real lines only • Today/Tomorrow games • All player cards • Advanced WNBA projection protection</div>
  <span class="badge good-badge">{APP_VERSION}</span>
  <span class="badge blue-badge">Underdog first</span>
  <span class="badge">No fake lines</span>
  <span class="badge">All props visible</span>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Controls")
    selected_day = st.radio("Game board", ["Today", "Tomorrow"], horizontal=True)
    source_choice = st.selectbox("Line source", ["Underdog first", "Underdog only", "PrizePicks backup only", "All available"], index=0)
    season = st.text_input("WNBA season", value=os.getenv("WNBA_SEASON", "2025"))
    refresh = st.button("🔄 Refresh board", use_container_width=True)

    st.divider()
    st.caption("Save workflow")
    save_tag = st.selectbox("Snapshot type", ["before", "after"], index=0)
    only_save = st.multiselect(
        "Save only signals",
        ["ELITE WATCH", "PASS", "LEAN", "NO BET"],
        default=["ELITE WATCH", "PASS", "LEAN"],
    )

    st.divider()
    st.caption("Filters")
    market_options = list(MARKET_LABELS.values())
    selected_markets = st.multiselect("Markets", market_options, default=market_options)
    signal_filter = st.multiselect(
        "Signals",
        ["ELITE WATCH", "PASS", "LEAN", "NO BET", "NO LINE"],
        default=["ELITE WATCH", "PASS", "LEAN", "NO BET"],
    )
    search_name = st.text_input("Search player", value="")
    show_all_cards = st.checkbox("Show all player cards", value=True)
    max_cards = st.slider("Max cards to render", 25, 300, 150)

if refresh:
    st.cache_data.clear()

with st.spinner("Pulling real WNBA lines, games, stats, and advanced context..."):
    games_today = get_wnba_scoreboard(today_str())
    games_tomorrow = get_wnba_scoreboard(tomorrow_str())
    prop_rows = fetch_all_real_wnba_props(source_choice)
    season_df = get_wnba_player_dashboard(season=season, last_n="0")
    last5_df = get_wnba_player_dashboard(season=season, last_n="5")
    last10_df = get_wnba_player_dashboard(season=season, last_n="10")
    team_df = get_wnba_team_dashboard(season=season)
    opp_df = get_wnba_team_opponent_dashboard(season=season)
    board_df = build_board(prop_rows, season_df, last5_df, last10_df, team_df, opp_df, games_today, games_tomorrow, selected_day)

if board_df.empty:
    st.markdown("""
    <div class="red-card">
    <b>No WNBA prop lines loaded.</b><br>
    The selected real source did not return WNBA props right now, or the source blocked the request.
    This app will not create fake lines.
    </div>
    """, unsafe_allow_html=True)
else:
    if selected_markets:
        board_df = board_df[board_df["Market Label"].isin(selected_markets)]
    if signal_filter:
        board_df = board_df[board_df["Signal"].isin(signal_filter)]
    if search_name.strip():
        board_df = board_df[board_df["Player"].str.lower().str.contains(search_name.lower(), na=False)]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Props shown", len(board_df))
    c2.metric("Game board", selected_day)
    c3.metric("Elite", int((board_df["Signal"] == "ELITE WATCH").sum()))
    c4.metric("Pass", int((board_df["Signal"] == "PASS").sum()))
    c5.metric("Lean", int((board_df["Signal"] == "LEAN").sum()))
    c6.metric("Stats loaded", "YES" if not season_df.empty else "LOW")

    save_rows = board_df[board_df["Signal"].isin(only_save)].to_dict("records") if only_save else board_df.to_dict("records")
    if st.button(f"💾 Save official {save_tag} snapshots", use_container_width=True):
        n = save_official_snapshots(save_rows, tag=save_tag)
        st.success(f"Saved {n} official {save_tag} snapshots.")

    tab_games, tab_cards, tab_table, tab_saved, tab_grade, tab_learning = st.tabs([
        "📅 Today/Tomorrow Games",
        "🃏 Player Cards",
        "📋 All Props Table",
        "💾 Saved/CLV",
        "✅ Grade Results",
        "🧠 Learning",
    ])

    with tab_games:
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Today")
            render_games(games_today, "Today")
        with g2:
            st.subheader("Tomorrow")
            render_games(games_tomorrow, "Tomorrow")

    with tab_cards:
        if show_all_cards:
            render_player_cards(board_df, max_cards=max_cards)
        else:
            render_player_cards(board_df[board_df["Signal"].isin(["ELITE WATCH", "PASS", "LEAN"])], max_cards=max_cards)

    with tab_table:
        display_cols = [
            "Player", "Team", "Opponent", "Market Label", "Line", "Consensus Line",
            "Projection", "Projected Minutes", "Edge", "Pick", "Fair Prob", "EV",
            "Kelly", "Data Score", "Lineup Score", "Signal", "Source", "Book Count",
            "Alt Line", "CLV Δ", "Line Δ", "Risk Notes",
        ]
        st.dataframe(board_df[display_cols], use_container_width=True, height=740)
        csv = board_df[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download current board CSV", csv, "wnba_current_board_v2.csv", "text/csv")

    with tab_saved:
        saved = pd.DataFrame(load_json(PICK_LOG, []))
        clv = pd.DataFrame(load_json(CLV_FILE, {}).values())
        st.subheader("Official saved snapshots")
        if saved.empty:
            st.info("No official snapshots saved yet.")
        else:
            st.dataframe(saved.tail(600), use_container_width=True, height=360)
        st.subheader("CLV tracker")
        if clv.empty:
            st.info("No CLV rows yet.")
        else:
            st.dataframe(clv.tail(600), use_container_width=True, height=300)

    with tab_grade:
        st.subheader("Grade a saved prop")
        with st.form("grade_form"):
            g_player = st.text_input("Player name")
            g_market_label = st.selectbox("Market", list(MARKET_LABELS.values()))
            inv_market = {v: k for k, v in MARKET_LABELS.items()}
            g_line = st.number_input("Saved line", min_value=0.0, max_value=100.0, step=0.5)
            g_actual = st.number_input("Actual result", min_value=0.0, max_value=150.0, step=0.5)
            g_source = st.text_input("Source filter optional", value="")
            submitted = st.form_submit_button("Grade and update learning")
            if submitted:
                n = save_grade(g_player, inv_market[g_market_label], g_line, g_actual, g_source or None)
                if n:
                    st.success(f"Graded {n} saved snapshot(s) and updated learning.")
                else:
                    st.warning("No matching saved snapshot found.")
        results = pd.DataFrame(load_json(RESULT_LOG, []))
        st.subheader("Recent graded results")
        if results.empty:
            st.info("No graded results yet.")
        else:
            st.dataframe(results.tail(600), use_container_width=True, height=360)

    with tab_learning:
        learn = load_json(LEARN_FILE, {})
        if not learn:
            st.info("Learning file is empty until you grade results.")
        else:
            learn_rows = []
            for k, v in learn.items():
                player, market = k.split("::", 1) if "::" in k else (k, "")
                learn_rows.append({
                    "Player": player,
                    "Market": market,
                    "Scale": v.get("scale"),
                    "Samples": v.get("samples"),
                    "Avg Residual": v.get("avg_residual"),
                    "Last Error %": v.get("last_error_pct"),
                    "Updated": v.get("updated_at"),
                })
            st.dataframe(pd.DataFrame(learn_rows), use_container_width=True, height=520)

with st.expander("Source request log"):
    req = pd.DataFrame(load_json(REQUEST_LOG_FILE, []))
    if req.empty:
        st.caption("No request issues logged.")
    else:
        st.dataframe(req.tail(120), use_container_width=True)
