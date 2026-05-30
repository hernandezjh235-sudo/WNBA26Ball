# -*- coding: utf-8 -*-
"""
WNBA ELITE PROP + MONEYLINE ENGINE — ONE FILE — v1.0
Built from the same architecture philosophy as MLB v11.17, but fully WNBA-only.

Markets:
- Player Points
- Player Rebounds
- Player Assists
- Moneyline

Core principles:
- Real stats only from public ESPN WNBA endpoints.
- Real prop lines only from Underdog / PrizePicks when available.
- Optional manual line override for testing only; clearly labeled MANUAL.
- No fake generated prop lines.
- Streamlit/Railway ready.

Run locally:
    streamlit run wnba_elite_prop_moneyline_engine.py

Railway start command:
    streamlit run wnba_elite_prop_moneyline_engine.py --server.address=0.0.0.0 --server.port=$PORT
"""

import os
import re
import io
import json
import math
import time
import html
import difflib
import unicodedata
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    import pytz
except Exception:
    pytz = None

APP_VERSION = "WNBA_ELITE_PROP_MONEYLINE_ENGINE_v1.1_UD2_INJURY_DVP_MINUTES_GATE"

# ============================================================
# STORAGE
# ============================================================
DRIVE_DIR = "/content/drive/MyDrive/wnba_engine"
LOCAL_DIR = "wnba_engine"
try:
    from google.colab import drive  # type: ignore
    if not os.path.exists("/content/drive/MyDrive"):
        drive.mount("/content/drive", force_remount=False)
    os.makedirs(DRIVE_DIR, exist_ok=True)
    STORAGE_DIR = DRIVE_DIR
except Exception:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    STORAGE_DIR = LOCAL_DIR

PICK_LOG = os.path.join(STORAGE_DIR, "wnba_pick_log.json")
RESULT_LOG = os.path.join(STORAGE_DIR, "wnba_result_log.json")
LEARN_FILE = os.path.join(STORAGE_DIR, "wnba_learning.json")
CLV_FILE = os.path.join(STORAGE_DIR, "wnba_clv_tracker.json")
LINE_HISTORY_FILE = os.path.join(STORAGE_DIR, "wnba_line_history.json")
REQUEST_LOG_FILE = os.path.join(STORAGE_DIR, "wnba_request_log.json")
CALIBRATION_FILE = os.path.join(STORAGE_DIR, "wnba_calibration.json")
UNDERDOG_DEBUG_FILE = os.path.join(STORAGE_DIR, "wnba_underdog_debug.json")
INJURY_CONTROL_FILE = os.path.join(STORAGE_DIR, "wnba_injury_controls.json")

# ============================================================
# DATA SOURCES
# ============================================================
ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba"
ESPN_COMMON = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba"
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"
UNDERDOG_URLS = [
    "https://api.underdogfantasy.com/beta/v6/over_under_lines",
    "https://api.underdogfantasy.com/beta/v5/over_under_lines",
    "https://api.underdogfantasy.com/beta/v4/over_under_lines",
    "https://api.underdogfantasy.com/beta/v3/over_under_lines",
    "https://api.underdogfantasy.com/v1/over_under_lines",
]
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ============================================================
# MODEL SETTINGS
# ============================================================
SIMS = 14000
ML_SIMS = 12000
MIN_BETTABLE_PROB = 0.635
MIN_BETTABLE_EDGE = {
    "Points": 1.25,
    "Rebounds": 0.85,
    "Assists": 0.65,
}
MIN_DATA_SCORE = 88
MIN_OFFICIAL_SAVE_SCORE = 88
MAX_RECOMMENDED_KELLY = 0.02
DEFAULT_ODDS = -110
CURRENT_SEASON = 2026

MARKETS = ["Points", "Rebounds", "Assists"]
STAT_KEYS = {"Points": "PTS", "Rebounds": "REB", "Assists": "AST"}
PROP_ALIASES = {
    "points": "Points", "pts": "Points", "player points": "Points",
    "rebounds": "Rebounds", "rebs": "Rebounds", "reb": "Rebounds", "player rebounds": "Rebounds",
    "assists": "Assists", "asts": "Assists", "ast": "Assists", "player assists": "Assists",
}
TEAM_ABBR_FIX = {
    "CON": "CONN", "CONN": "CONN", "LAS": "LV", "LVA": "LV", "LV": "LV",
    "NYL": "NY", "NY": "NY", "PHO": "PHX", "PHX": "PHX", "WSH": "WAS", "WAS": "WAS",
}

# ============================================================
# STREAMLIT CONFIG + UI
# ============================================================
st.set_page_config(
    page_title="WNBA Elite Prop + Moneyline Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top,#101b30 0%,#080b12 42%,#020307 100%); color:#fff;}
.block-container {padding-top:1.0rem; max-width:1550px;}
h1,h2,h3 {color:#fff;}
[data-testid="stMetric"] {
    background:linear-gradient(145deg,#0d1420,#09111c);
    border:1px solid rgba(61,150,255,.34);
    border-radius:18px;
    padding:15px;
    box-shadow:0 0 18px rgba(0,120,255,.12);
}
.hero-panel {
    background:linear-gradient(135deg,rgba(11,38,70,.94),rgba(6,8,13,.97));
    border:1px solid rgba(92,178,255,.38);
    border-radius:26px;
    padding:22px;
    box-shadow:0 0 34px rgba(0,120,255,.14);
    margin-bottom:18px;
}
.pick-card {
    background:linear-gradient(145deg,#0b1019,#0d1622);
    border:1px solid rgba(92,178,255,.30);
    border-radius:22px;
    padding:20px;
    box-shadow:0 0 24px rgba(0,120,255,.11);
    margin-bottom:16px;
}
.green-card {background:linear-gradient(145deg,#001b0e,#07110b);border:1px solid rgba(0,255,135,.46);border-radius:22px;padding:20px;box-shadow:0 0 28px rgba(0,255,135,.18);margin-bottom:16px;}
.warn-card {background:linear-gradient(145deg,#1e1604,#11100b);border:1px solid rgba(255,190,60,.42);border-radius:22px;padding:20px;box-shadow:0 0 22px rgba(255,190,60,.10);margin-bottom:16px;}
.small-muted {color:#b7c1cd; font-size:13px;}
.big-title {font-size:40px; font-weight:950; color:#fff; letter-spacing:-1px;}
.sub-title {color:#c8d2dd; font-size:15px; margin-top:-6px;}
.player-name {font-size:23px; font-weight:900; color:#fff;}
.big-number {font-size:42px; font-weight:950; line-height:1.05;}
.green {color:#31e84f;} .orange {color:#ffbe3c;} .red {color:#ff5f5f;} .blue {color:#66b7ff;}
.badge {display:inline-block;padding:6px 12px;border-radius:999px;background:#081c33;border:1px solid rgba(100,180,255,.45);color:#cce9ff;font-weight:800;margin:3px 4px 3px 0;}
.good-badge {background:#002916;border-color:rgba(0,255,135,.55);color:#b5ffd9;}
.yellow-badge {background:#2b1d00;border-color:rgba(255,210,70,.55);color:#ffe2a1;}
.red-badge {background:#2b0000;border-color:rgba(255,75,75,.55);color:#ffc0c0;}
.kpi-strip {display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap:12px; margin:12px 0 18px 0;}
.kpi-box {background:linear-gradient(145deg,#0b1019,#0d1622);border:1px solid rgba(92,178,255,.25);border-radius:18px;padding:14px;min-height:92px;}
.kpi-label {font-size:12px;color:#aeb7c2;font-weight:800;letter-spacing:.04em;text-transform:uppercase;}
.kpi-value {font-size:26px;font-weight:900;color:#fff;margin-top:6px;}
.kpi-sub {font-size:12px;color:#cbd2db;margin-top:5px;}
.hr-soft {border-top:1px solid rgba(255,255,255,.12); margin:14px 0;}
.section-title-pro {margin-top:22px;margin-bottom:10px;font-size:24px;font-weight:950;color:#fff;border-left:5px solid #66b7ff;padding-left:12px;}
.stTabs [data-baseweb="tab"] {color:#b8c3cf;font-weight:850;}
.stTabs [aria-selected="true"] {color:#31e84f!important;border-bottom:3px solid #31e84f;}
@media (max-width: 900px) {.kpi-strip {grid-template-columns: repeat(2, minmax(0, 1fr));}.big-title{font-size:30px}.block-container{padding-left:.65rem!important;padding-right:.65rem!important}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPERS
# ============================================================
def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

ODDS_API_KEY = get_secret("ODDS_API_KEY", "")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def california_now() -> datetime:
    if pytz:
        return datetime.now(pytz.timezone("America/Los_Angeles"))
    return datetime.utcnow() - timedelta(hours=7)


def safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None or x == "" or str(x).lower() in ["nan", "none", "null"]:
            return default
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def load_json(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path: str, data: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def log_source_request(source: str, status: str, message: str = "") -> None:
    rows = load_json(REQUEST_LOG_FILE, [])
    rows.append({"time": now_iso(), "source": str(source)[:220], "status": str(status)[:100], "message": str(message)[:500]})
    save_json(REQUEST_LOG_FILE, rows[-800:])


def strip_accents(text: Any) -> str:
    try:
        return "".join(ch for ch in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(ch))
    except Exception:
        return str(text or "")


def normalize_name(name: Any) -> str:
    s = strip_accents(name).lower().strip()
    for ch in [".", ",", "'", "-", "_", " jr", " sr", " ii", " iii", " iv"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def name_score(a: Any, b: Any) -> float:
    a_norm, b_norm = normalize_name(a), normalize_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.94
    a_parts, b_parts = a_norm.split(), b_norm.split()
    if a_parts and b_parts and a_parts[-1] == b_parts[-1] and a_parts[0][:1] == b_parts[0][:1]:
        return 0.93
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


def clean_team_abbr(x: Any) -> str:
    s = str(x or "").upper().strip()
    return TEAM_ABBR_FIX.get(s, s)


def fmt(x: Any, digits: int = 2, default: str = "—") -> str:
    v = safe_float(x)
    if v is None:
        return default
    return f"{v:.{digits}f}"


@st.cache_data(ttl=300, show_spinner=False)
def safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15, headers: Optional[Dict[str, str]] = None) -> Any:
    try:
        h = {
            "User-Agent": "Mozilla/5.0 WNBAElitePropEngine/1.0",
            "Accept": "application/json,text/plain,*/*",
        }
        if headers:
            h.update(headers)
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        if r.status_code != 200:
            log_source_request(url, f"HTTP {r.status_code}", r.text[:300])
            return None
        try:
            return r.json()
        except Exception as e:
            log_source_request(url, "BAD_JSON", str(e))
            return None
    except Exception as e:
        log_source_request(url, "REQUEST_ERROR", str(e))
        return None


def flatten_json(obj: Any) -> List[dict]:
    items: List[dict] = []
    if isinstance(obj, dict):
        items.append(obj)
        for v in obj.values():
            items.extend(flatten_json(v))
    elif isinstance(obj, list):
        for x in obj:
            items.extend(flatten_json(x))
    return items

# ============================================================
# BETTING MATH
# ============================================================
def american_to_implied(price: Any) -> Optional[float]:
    price = safe_float(price)
    if price is None:
        return None
    return 100 / (price + 100) if price > 0 else abs(price) / (abs(price) + 100)


def decimal_odds(odds: Any) -> Optional[float]:
    odds = safe_float(odds)
    if odds is None:
        return None
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def expected_value(prob: Optional[float], odds: Any) -> Optional[float]:
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return None
    return (prob * (dec - 1)) - (1 - prob)


def kelly_fraction(prob: Optional[float], odds: Any) -> float:
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return 0.0
    b = dec - 1
    q = 1 - prob
    if b <= 0:
        return 0.0
    return float(clamp(((b * prob) - q) / b, 0, 0.25))


def no_vig_pair_prob(price_a: Optional[float], price_b: Optional[float]) -> Optional[float]:
    ia = american_to_implied(price_a)
    ib = american_to_implied(price_b)
    if ia is None or ib is None or ia + ib <= 0:
        return ia
    return ia / (ia + ib)

# ============================================================
# ESPN WNBA DATA
# ============================================================
def target_dates(day_mode: str) -> List[str]:
    now = california_now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if day_mode == "Today":
        return [today]
    if day_mode == "Tomorrow":
        return [tomorrow]
    return [today, tomorrow]


def espn_date(date_str: str) -> str:
    return date_str.replace("-", "")


@st.cache_data(ttl=300, show_spinner=False)
def get_scoreboard(date_str: str) -> Dict[str, Any]:
    return safe_get_json(f"{ESPN_SITE}/scoreboard", params={"dates": espn_date(date_str), "limit": 50}) or {"events": []}


@st.cache_data(ttl=900, show_spinner=False)
def get_teams() -> pd.DataFrame:
    data = safe_get_json(f"{ESPN_SITE}/teams", params={"limit": 50}) or {}
    rows = []
    sports = data.get("sports") or []
    for sport in sports:
        for league in sport.get("leagues", []) or []:
            for t in league.get("teams", []) or []:
                team = t.get("team") or t
                rows.append({
                    "team_id": str(team.get("id") or ""),
                    "team": team.get("displayName") or team.get("name"),
                    "abbr": clean_team_abbr(team.get("abbreviation") or team.get("shortDisplayName")),
                    "location": team.get("location"),
                    "color": team.get("color"),
                })
    return pd.DataFrame(rows).drop_duplicates(subset=["team_id"]) if rows else pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def get_team_roster(team_id: str) -> pd.DataFrame:
    urls = [
        f"{ESPN_SITE}/teams/{team_id}/roster",
        f"{ESPN_COMMON}/teams/{team_id}/roster",
    ]
    rows = []
    for url in urls:
        data = safe_get_json(url, params={"enable": "roster"}) or {}
        athletes = data.get("athletes") or data.get("team", {}).get("athletes") or []
        if isinstance(athletes, dict):
            athletes = athletes.get("items") or []
        for a in athletes:
            athlete = a.get("athlete") if isinstance(a, dict) and "athlete" in a else a
            if not isinstance(athlete, dict):
                continue
            pos = athlete.get("position") or {}
            rows.append({
                "player_id": str(athlete.get("id") or ""),
                "player": athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"),
                "team_id": str(team_id),
                "position": pos.get("abbreviation") or pos.get("name") or "",
                "height": athlete.get("height"),
                "weight": athlete.get("weight"),
                "status": (athlete.get("status") or {}).get("name") if isinstance(athlete.get("status"), dict) else athlete.get("status"),
            })
        if rows:
            break
    return pd.DataFrame(rows).drop_duplicates(subset=["player_id"]) if rows else pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def get_all_rosters() -> pd.DataFrame:
    teams = get_teams()
    frames = []
    if teams.empty:
        return pd.DataFrame()
    for _, t in teams.iterrows():
        r = get_team_roster(str(t["team_id"]))
        if not r.empty:
            r["team"] = t["team"]
            r["abbr"] = t["abbr"]
            frames.append(r)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parse_competitor(comp: Dict[str, Any]) -> Dict[str, Any]:
    team = comp.get("team") or {}
    return {
        "team_id": str(team.get("id") or ""),
        "team": team.get("displayName") or team.get("name"),
        "abbr": clean_team_abbr(team.get("abbreviation") or team.get("shortDisplayName")),
        "home_away": comp.get("homeAway"),
        "score": safe_float(comp.get("score")),
        "winner": comp.get("winner"),
        "record": ", ".join([r.get("summary", "") for r in comp.get("records", []) if r.get("summary")]),
    }


def extract_games(date_strs: List[str]) -> pd.DataFrame:
    rows = []
    for ds in date_strs:
        data = get_scoreboard(ds)
        for e in data.get("events", []) or []:
            comp = (e.get("competitions") or [{}])[0]
            competitors = comp.get("competitors") or []
            home = next((parse_competitor(c) for c in competitors if c.get("homeAway") == "home"), None)
            away = next((parse_competitor(c) for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            status = comp.get("status") or e.get("status") or {}
            status_type = status.get("type") or {}
            rows.append({
                "date": ds,
                "event_id": str(e.get("id") or comp.get("id") or ""),
                "game_time": e.get("date"),
                "name": e.get("name") or f"{away['abbr']} @ {home['abbr']}",
                "short_name": e.get("shortName") or f"{away['abbr']} @ {home['abbr']}",
                "status": status_type.get("description") or status_type.get("name") or "Scheduled",
                "completed": bool(status_type.get("completed")),
                "neutral": comp.get("neutralSite", False),
                "venue": (comp.get("venue") or {}).get("fullName") or "",
                "home_team": home["team"], "home_abbr": home["abbr"], "home_id": home["team_id"], "home_score": home["score"],
                "away_team": away["team"], "away_abbr": away["abbr"], "away_id": away["team_id"], "away_score": away["score"],
                "matchup": f"{away['abbr']} @ {home['abbr']}",
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def get_player_gamelog(player_id: str, season: int = CURRENT_SEASON) -> pd.DataFrame:
    urls = [
        f"{ESPN_COMMON}/athletes/{player_id}/gamelog",
        f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/{player_id}/gamelog",
    ]
    data = None
    for url in urls:
        data = safe_get_json(url, params={"season": season})
        if data:
            break
    rows = []
    if not isinstance(data, dict):
        return pd.DataFrame()

    # ESPN common gamelog usually returns seasonTypes -> categories -> events.
    events_by_id = {}
    for ev in (data.get("events") or {}).values() if isinstance(data.get("events"), dict) else data.get("events", []):
        if isinstance(ev, dict):
            events_by_id[str(ev.get("id") or ev.get("eventId") or "")] = ev

    def add_row_from_stats(ev_id: str, stat_map: Dict[str, Any], ev_meta: Dict[str, Any]) -> None:
        def grab(*keys):
            for k in keys:
                if k in stat_map:
                    return safe_float(stat_map[k])
                for kk, vv in stat_map.items():
                    if str(kk).lower() == str(k).lower():
                        return safe_float(vv)
            return None
        rows.append({
            "Date": ev_meta.get("gameDate") or ev_meta.get("date") or ev_meta.get("eventDate"),
            "EventID": ev_id,
            "Opponent": ((ev_meta.get("opponent") or {}).get("displayName") if isinstance(ev_meta.get("opponent"), dict) else ev_meta.get("opponent")) or "",
            "HomeAway": ev_meta.get("homeAway") or "",
            "MIN": grab("MIN", "min", "minutes"),
            "PTS": grab("PTS", "points"),
            "REB": grab("REB", "rebounds", "TOT"),
            "AST": grab("AST", "assists"),
            "FGA": grab("FGA", "fieldGoalsAttempted"),
            "FGM": grab("FGM", "fieldGoalsMade"),
            "FTA": grab("FTA", "freeThrowsAttempted"),
            "TOV": grab("TO", "TOV", "turnovers"),
            "STL": grab("STL", "steals"),
            "BLK": grab("BLK", "blocks"),
        })

    # Format A: seasonTypes/categories/events
    for season_type in data.get("seasonTypes", []) or []:
        for cat in season_type.get("categories", []) or []:
            for ev in cat.get("events", []) or []:
                ev_id = str(ev.get("eventId") or ev.get("id") or "")
                stats = ev.get("stats") or ev.get("stat") or {}
                ev_meta = events_by_id.get(ev_id, ev)
                if isinstance(stats, dict):
                    add_row_from_stats(ev_id, stats, ev_meta)
                elif isinstance(stats, list):
                    # Sometimes stats are list values with labels held elsewhere. Use common basketball order fallback.
                    labels = ["MIN", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "REB", "AST", "BLK", "STL", "PF", "TOV", "PTS"]
                    stat_map = {labels[i]: stats[i] for i in range(min(len(labels), len(stats)))}
                    add_row_from_stats(ev_id, stat_map, ev_meta)

    # Format B: direct events list with stats.
    if not rows:
        for ev in data.get("events", []) if isinstance(data.get("events"), list) else []:
            ev_id = str(ev.get("id") or ev.get("eventId") or "")
            stats = ev.get("stats") or {}
            if isinstance(stats, dict):
                add_row_from_stats(ev_id, stats, ev)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["MIN", "PTS", "REB", "AST", "FGA", "FGM", "FTA", "TOV", "STL", "BLK"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df = df.dropna(subset=["MIN", "PTS", "REB", "AST"], how="all")
    # Newest first if date parses.
    try:
        df["_date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("_date", ascending=False).drop(columns=["_date"])
    except Exception:
        pass
    return df.drop_duplicates(subset=["EventID", "PTS", "REB", "AST"], keep="first")


@st.cache_data(ttl=1200, show_spinner=False)
def get_event_summary(event_id: str) -> Dict[str, Any]:
    return safe_get_json(f"{ESPN_SITE}/summary", params={"event": event_id}) or {}


def boxscore_player_rows(event_id: str) -> pd.DataFrame:
    data = get_event_summary(event_id)
    rows = []
    box = data.get("boxscore") or {}
    for team_block in box.get("players", []) or []:
        team = team_block.get("team") or {}
        abbr = clean_team_abbr(team.get("abbreviation"))
        for stat_group in team_block.get("statistics", []) or []:
            labels = stat_group.get("labels") or []
            if not labels:
                continue
            for athlete in stat_group.get("athletes", []) or []:
                a = athlete.get("athlete") or {}
                stats = athlete.get("stats") or []
                m = {labels[i]: stats[i] for i in range(min(len(labels), len(stats)))}
                rows.append({
                    "player_id": str(a.get("id") or ""),
                    "player": a.get("displayName") or a.get("fullName") or a.get("shortName"),
                    "team_abbr": abbr,
                    "MIN": safe_float(m.get("MIN")),
                    "PTS": safe_float(m.get("PTS")),
                    "REB": safe_float(m.get("REB")),
                    "AST": safe_float(m.get("AST")),
                    "FGA": safe_float(m.get("FGA")),
                    "FGM": safe_float(m.get("FGM")),
                    "FTA": safe_float(m.get("FTA")),
                    "TOV": safe_float(m.get("TO") or m.get("TOV")),
                })
    return pd.DataFrame(rows)

# ============================================================
# PROP LINES — UNDERDOG + PRIZEPICKS
# ============================================================
def market_from_text(text: Any) -> Optional[str]:
    t = normalize_name(text).replace(" ", " ")
    raw = str(text or "").lower()
    for k, v in PROP_ALIASES.items():
        if k in raw:
            # Avoid combos for now.
            if any(combo in raw for combo in ["pra", "pts+reb", "points + rebounds", "rebounds + assists", "fantasy"]):
                return None
            return v
    return None


def is_wnba_text(text: Any) -> bool:
    t = str(text or "").lower()
    return "wnba" in t or "women" in t or "basketball" in t


@st.cache_data(ttl=120, show_spinner=False)
def fetch_prizepicks_lines() -> pd.DataFrame:
    data = safe_get_json(PRIZEPICKS_URL, timeout=18)
    if not isinstance(data, dict):
        return pd.DataFrame()
    included = data.get("included") or []
    players: Dict[str, Dict[str, Any]] = {}
    for inc in included:
        if inc.get("type") == "new_player":
            attrs = inc.get("attributes") or {}
            players[str(inc.get("id"))] = {
                "player": attrs.get("name") or attrs.get("display_name"),
                "team": attrs.get("team"),
                "league": attrs.get("league"),
                "position": attrs.get("position"),
            }
    rows = []
    for item in data.get("data", []) or []:
        attrs = item.get("attributes") or {}
        rel = item.get("relationships") or {}
        p_id = None
        try:
            p_id = str(rel.get("new_player", {}).get("data", {}).get("id"))
        except Exception:
            p_id = None
        p = players.get(str(p_id), {})
        league = str(attrs.get("league") or p.get("league") or "").upper()
        stat_type = attrs.get("stat_type") or attrs.get("statType") or attrs.get("name")
        market = market_from_text(stat_type)
        if league != "WNBA" or market is None:
            continue
        line = safe_float(attrs.get("line_score") or attrs.get("line"))
        if line is None:
            continue
        rows.append({
            "Player": p.get("player") or attrs.get("description"),
            "Market": market,
            "Line": line,
            "Source": "PrizePicks",
            "Price": DEFAULT_ODDS,
            "Team": p.get("team"),
            "Raw": stat_type,
        })
    return pd.DataFrame(rows).drop_duplicates(subset=["Player", "Market", "Source"]) if rows else pd.DataFrame()



@st.cache_data(ttl=90, show_spinner=False)
def fetch_underdog_lines() -> pd.DataFrame:
    """Verified Underdog Matching 2.0.

    Goals:
    - WNBA-only rows. Reject NBA/NCAAB/NFL contamination.
    - Market lock to player Points/Rebounds/Assists only.
    - Store a debug table for every possible UD prop row seen.
    - Return only rows with a real player, real market, and real line.
    """
    rows: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []

    def blob_text(obj: Any, limit: int = 9000) -> str:
        try:
            return json.dumps(obj, ensure_ascii=False).lower()[:limit]
        except Exception:
            return str(obj).lower()[:limit]

    def strict_market_from_ud_text(text: Any) -> Optional[str]:
        raw = str(text or "").lower()
        # hard reject combo/discount/fantasy/stat mashups
        bad = [
            "pra", "points+rebounds", "points + rebounds", "pts+reb", "pts + reb",
            "rebounds+assists", "rebounds + assists", "reb+ast", "reb + ast",
            "points+assists", "points + assists", "pts+ast", "pts + ast",
            "fantasy", "combo", "rival", "special", "discount", "double double",
            "triple double", "made threes", "3-pointers", "turnovers", "steals", "blocks"
        ]
        if any(x in raw for x in bad):
            return None
        # exact-ish market lock
        if re.search(r"\b(player\s+)?(points|pts)\b", raw):
            return "Points"
        if re.search(r"\b(player\s+)?(rebounds|rebs|reb)\b", raw):
            return "Rebounds"
        if re.search(r"\b(player\s+)?(assists|asts|ast)\b", raw):
            return "Assists"
        return None

    def is_strict_wnba(obj: Any) -> bool:
        b = blob_text(obj)
        # WNBA accepted; NBA/NCAAB/etc rejected unless WNBA explicitly present and no male NBA markers dominate.
        if "wnba" not in b and "women" not in b:
            return False
        bad = ["\"nba\"", " ncaab", "college basketball", "mens", "men's", " nfl", " mlb", " nhl"]
        if "wnba" in b:
            return True
        return not any(x in b for x in bad)

    def extract_line(d: Dict[str, Any]) -> Optional[float]:
        for k in ["line", "stat_value", "over_under_line", "value", "line_score", "target", "over_under_value"]:
            if k in d:
                v = safe_float(d.get(k))
                if v is not None and 0 <= v <= 60:
                    return v
        return None

    def clean_ud_player_name(name: Any, market: Optional[str]) -> str:
        txt = str(name or "").strip()
        # Remove market and side text embedded in some titles.
        kill = ["Higher", "Lower", "Over", "Under", "Points", "Rebounds", "Assists", "PTS", "REB", "AST", "WNBA"]
        for word in kill:
            txt = re.sub(rf"\b{re.escape(word)}\b", " ", txt, flags=re.I)
        txt = re.sub(r"\s+", " ", txt).strip(" -|•:")
        return txt

    for url in UNDERDOG_URLS:
        data = safe_get_json(url, timeout=18)
        if not data:
            continue
        flat = flatten_json(data)

        player_map: Dict[str, str] = {}
        for d in flat:
            if not isinstance(d, dict):
                continue
            name = d.get("display_name") or d.get("full_name") or d.get("name") or d.get("title")
            if d.get("first_name") or d.get("last_name"):
                name = f"{d.get('first_name','')} {d.get('last_name','')}".strip()
            ids = [d.get("id"), d.get("player_id"), d.get("appearance_id")]
            try:
                ids.append((d.get("appearance") or {}).get("id"))
            except Exception:
                pass
            if name:
                for pid in ids:
                    if pid is not None:
                        player_map[str(pid)] = str(name)

        for d in flat:
            if not isinstance(d, dict):
                continue
            text_parts = []
            for k in ["stat", "stat_type", "stat_type_name", "display_stat", "title", "over_under", "appearance_stat", "description", "name"]:
                if k in d:
                    text_parts.append(str(d.get(k)))
            stat_text = " ".join(text_parts)
            market = strict_market_from_ud_text(stat_text)
            line = extract_line(d)
            wnba_ok = is_strict_wnba(d)

            raw_name = d.get("player_name") or d.get("display_name") or d.get("player") or d.get("athlete") or d.get("title") or d.get("name")
            for key in ["player_id", "appearance_id", "over_under_id", "appearance_stat_id"]:
                if (not raw_name or str(raw_name).strip() == "") and d.get(key) is not None:
                    raw_name = player_map.get(str(d.get(key)))
            player = clean_ud_player_name(raw_name, market)

            accepted = bool(wnba_ok and market is not None and line is not None and player and len(player.split()) >= 2)
            debug.append({
                "Accepted": accepted,
                "URL": url,
                "Player Raw": str(raw_name)[:120],
                "Player Clean": player,
                "Market": market,
                "Line": line,
                "WNBA Filter": wnba_ok,
                "Raw Market Text": stat_text[:220],
                "Reject Reason": "" if accepted else (
                    "not WNBA" if not wnba_ok else "bad market" if market is None else "bad line" if line is None else "bad player"
                ),
            })
            if not accepted:
                continue
            rows.append({
                "Player": player,
                "Market": market,
                "Line": float(line),
                "Source": "Underdog",
                "Price": DEFAULT_ODDS,
                "Team": d.get("team") or d.get("team_abbr") or d.get("team_name"),
                "Raw": stat_text[:160],
                "Verified": True,
            })

        if rows:
            break

    try:
        save_json(UNDERDOG_DEBUG_FILE, debug[-1500:])
    except Exception:
        pass

    if not rows:
        return pd.DataFrame(columns=["Player", "Market", "Line", "Source", "Price", "Team", "Raw", "Verified"])
    out = pd.DataFrame(rows)
    out["_name"] = out["Player"].apply(normalize_name)
    out = out.drop_duplicates(subset=["_name", "Market", "Source"], keep="first").drop(columns=["_name"])
    return out


def fetch_all_prop_lines() -> pd.DataFrame:
    frames = []
    pp = fetch_prizepicks_lines()
    ud = fetch_underdog_lines()
    if not pp.empty:
        frames.append(pp)
    if not ud.empty:
        frames.append(ud)
    if frames:
        return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Player", "Market", "Source"])
    return pd.DataFrame(columns=["Player", "Market", "Line", "Source", "Price", "Team", "Raw"])


def best_line_for_player(player: str, market: str, lines: pd.DataFrame, preferred: str = "Underdog") -> Optional[Dict[str, Any]]:
    """Return a real vendor line only when the player+market match is strong.

    This intentionally shows NO UD LINE / NO REAL LINE instead of forcing a weak match.
    """
    if lines.empty:
        return None
    candidates = lines[lines["Market"].eq(market)].copy()
    if candidates.empty:
        return None
    candidates["score"] = candidates["Player"].apply(lambda x: name_score(player, x))
    # Underdog must be stricter because public feeds can contain abbreviations and stale titles.
    candidates["min_score"] = candidates["Source"].astype(str).str.lower().map(lambda s: 0.90 if s == "underdog" else 0.86)
    candidates = candidates[candidates["score"] >= candidates["min_score"]].sort_values(["score", "Source"], ascending=[False, True])
    if candidates.empty:
        return None
    pref = candidates[candidates["Source"].str.lower().eq(preferred.lower())]
    row = pref.iloc[0] if not pref.empty else candidates.iloc[0]
    return row.to_dict()


# ============================================================
# INJURY RIPPLE + DEFENSE VS POSITION 2.0
# ============================================================
def normalize_injury_status(status: Any) -> str:
    t = str(status or "").strip().upper()
    if not t:
        return "ACTIVE"
    if t in ["OUT", "INACTIVE", "INJURED"] or "OUT" in t:
        return "OUT"
    if t in ["QUESTIONABLE", "Q", "GTD", "GAME TIME DECISION"] or "QUESTION" in t or "GTD" in t:
        return "QUESTIONABLE"
    if "LIMIT" in t or "RESTRICT" in t:
        return "MINUTES LIMIT"
    return t


def sanitize_injury_controls(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Player", "Team", "Status", "Minutes Limit", "Team ML Adj", "Notes"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = "" if c not in ["Minutes Limit", "Team ML Adj"] else None
    out = out[cols].copy()
    out["Player"] = out["Player"].fillna("").astype(str)
    out["Team"] = out["Team"].fillna("").astype(str).apply(clean_team_abbr)
    out["Status"] = out["Status"].fillna("ACTIVE").apply(normalize_injury_status)
    out["Minutes Limit"] = pd.to_numeric(out["Minutes Limit"], errors="coerce")
    out["Team ML Adj"] = pd.to_numeric(out["Team ML Adj"], errors="coerce").fillna(0.0)
    out = out[(out["Player"].str.strip() != "") | (out["Team"].str.strip() != "")].copy()
    return out


def injury_row_for_player(player: str, team: str, injury_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if injury_df is None or injury_df.empty:
        return None
    team = clean_team_abbr(team)
    df = injury_df.copy()
    df["_team_ok"] = df["Team"].astype(str).apply(clean_team_abbr).eq(team) | df["Team"].astype(str).eq("")
    df["_score"] = df["Player"].apply(lambda x: name_score(player, x) if str(x).strip() else 0.0)
    df = df[(df["_team_ok"]) & (df["_score"] >= 0.88)].sort_values("_score", ascending=False)
    if df.empty:
        return None
    return df.iloc[0].drop(labels=["_team_ok", "_score"]).to_dict()


def team_injury_ripple(team: str, injury_df: pd.DataFrame) -> Dict[str, float]:
    if injury_df is None or injury_df.empty:
        return {"out_count": 0, "q_count": 0, "limit_count": 0, "teammate_min_boost": 0.0, "usage_boost": 1.0, "ml_adj": 0.0}
    team = clean_team_abbr(team)
    df = injury_df[injury_df["Team"].astype(str).apply(clean_team_abbr).eq(team)].copy()
    out_count = int(df["Status"].eq("OUT").sum()) if not df.empty else 0
    q_count = int(df["Status"].eq("QUESTIONABLE").sum()) if not df.empty else 0
    limit_count = int(df["Status"].eq("MINUTES LIMIT").sum()) if not df.empty else 0
    manual_ml = float(pd.to_numeric(df.get("Team ML Adj", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
    # Default team penalty in projected margin points. Manual value stacks on top.
    ml_adj = manual_ml - (3.5 * out_count) - (1.25 * q_count) - (1.75 * limit_count)
    min_boost = clamp(out_count * 1.7 + q_count * 0.55 + limit_count * 0.75, 0.0, 4.5)
    usage_boost = clamp(1.0 + out_count * 0.025 + q_count * 0.010 + limit_count * 0.012, 1.0, 1.10)
    return {"out_count": out_count, "q_count": q_count, "limit_count": limit_count, "teammate_min_boost": min_boost, "usage_boost": usage_boost, "ml_adj": ml_adj}


def apply_player_injury_adjustment(player: str, team: str, exp_min: float, injury_df: pd.DataFrame) -> Tuple[float, str, int, str]:
    """Apply direct player injury control and teammate ripple. Returns minutes, risk, confidence penalty, note."""
    risk = "ACTIVE"
    penalty = 0
    notes: List[str] = []
    row = injury_row_for_player(player, team, injury_df)
    if row:
        status = normalize_injury_status(row.get("Status"))
        limit = safe_float(row.get("Minutes Limit"))
        if status == "OUT":
            exp_min = 0.0
            risk = "OUT_MANUAL"
            penalty += 60
            notes.append("Manual OUT")
        elif status == "QUESTIONABLE":
            exp_min *= 0.82
            risk = "QUESTIONABLE_MANUAL"
            penalty += 18
            notes.append("Manual QUESTIONABLE")
        elif status == "MINUTES LIMIT":
            if limit is not None:
                exp_min = min(exp_min, limit)
            else:
                exp_min *= 0.78
            risk = "MINUTES_LIMIT_MANUAL"
            penalty += 24
            notes.append("Manual MINUTES LIMIT")
    ripple = team_injury_ripple(team, injury_df)
    # Teammate redistribution: only players not directly marked OUT get extra volume.
    if not row or normalize_injury_status(row.get("Status")) != "OUT":
        if ripple["teammate_min_boost"] > 0:
            exp_min += ripple["teammate_min_boost"]
            notes.append(f"Teammate ripple +{ripple['teammate_min_boost']:.1f} min")
    return float(clamp(exp_min, 0, 42)), risk, penalty, "; ".join(notes) if notes else "No manual injury adjustment"


@st.cache_data(ttl=600, show_spinner=False)
def build_defense_vs_position() -> Dict[str, Dict[str, Dict[str, float]]]:
    """Estimate opponent allowed PTS/REB/AST to Guard/Wing/Post from recent ESPN boxscores."""
    today = california_now().date()
    date_list = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 22)]
    rosters = get_all_rosters()
    pos_map: Dict[Tuple[str, str], str] = {}
    if not rosters.empty:
        for _, r in rosters.iterrows():
            pos_map[(clean_team_abbr(r.get("team_abbr")), normalize_name(r.get("player")))] = position_bucket(r.get("position"))
    agg: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
    for ds in date_list:
        gdf = extract_games([ds])
        if gdf.empty:
            continue
        for _, g in gdf.iterrows():
            if not bool(g.get("completed")):
                continue
            box = fetch_event_boxscore(str(g.get("event_id")))
            if box.empty:
                continue
            for _, pr in box.iterrows():
                team = clean_team_abbr(pr.get("team_abbr"))
                if team == clean_team_abbr(g.get("home_abbr")):
                    opp = clean_team_abbr(g.get("away_abbr"))
                elif team == clean_team_abbr(g.get("away_abbr")):
                    opp = clean_team_abbr(g.get("home_abbr"))
                else:
                    continue
                bucket = pos_map.get((team, normalize_name(pr.get("player"))), "Wing")
                agg.setdefault(opp, {}).setdefault(bucket, {"Points": [], "Rebounds": [], "Assists": []})
                agg[opp][bucket]["Points"].append(safe_float(pr.get("PTS"), 0.0) or 0.0)
                agg[opp][bucket]["Rebounds"].append(safe_float(pr.get("REB"), 0.0) or 0.0)
                agg[opp][bucket]["Assists"].append(safe_float(pr.get("AST"), 0.0) or 0.0)
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for opp, by_pos in agg.items():
        out[opp] = {}
        for bucket, mkts in by_pos.items():
            out[opp][bucket] = {}
            for market, vals in mkts.items():
                # Per player appearance allowed by role. Baselines handled in matchup function.
                out[opp][bucket][market] = float(np.mean(vals)) if vals else np.nan
                out[opp][bucket][f"{market}_n"] = float(len(vals))
    return out

# ============================================================
# WNBA PROJECTION ENGINES
# ============================================================
def weighted_recent(series: pd.Series, default: Optional[float] = None) -> Optional[float]:
    vals = pd.to_numeric(series, errors="coerce").dropna().tolist()
    if not vals:
        return default
    l3 = float(np.mean(vals[:3])) if len(vals[:3]) else None
    l5 = float(np.mean(vals[:5])) if len(vals[:5]) else None
    l10 = float(np.mean(vals[:10])) if len(vals[:10]) else None
    parts = []
    if l3 is not None: parts.append((l3, 0.55))
    if l5 is not None: parts.append((l5, 0.30))
    if l10 is not None: parts.append((l10, 0.15))
    total = sum(w for _, w in parts)
    return sum(v * w for v, w in parts) / total if total else default


def position_bucket(pos: Any) -> str:
    p = str(pos or "").upper()
    if p in ["PG", "SG", "G"]:
        return "Guard"
    if p in ["SF", "F", "GF"]:
        return "Wing"
    if p in ["PF", "C", "FC"]:
        return "Post"
    return "Wing"


def minutes_engine(logs: pd.DataFrame, status: str = "") -> Dict[str, Any]:
    if logs.empty:
        return {"expected_minutes": 18.0, "confidence": 35, "risk": "UNKNOWN", "note": "No ESPN game log; fallback minutes"}
    mins = pd.to_numeric(logs["MIN"], errors="coerce").dropna()
    if mins.empty:
        return {"expected_minutes": 18.0, "confidence": 35, "risk": "UNKNOWN", "note": "No minute data; fallback"}
    exp_min = weighted_recent(mins, float(mins.mean())) or 18.0
    last3 = mins.head(3).tolist()
    std = float(np.std(mins.head(min(10, len(mins))).tolist())) if len(mins) >= 2 else 4.0
    risk = "SECURE"
    confidence = 78
    if exp_min < 18:
        risk = "LOW_MINUTES"; confidence -= 22
    elif exp_min < 24:
        risk = "MODERATE"; confidence -= 10
    if std >= 8:
        risk = "VOLATILE_MINUTES"; confidence -= 14
    elif std >= 5.5:
        confidence -= 7
    stxt = str(status or "").lower()
    if any(x in stxt for x in ["out", "injured", "inactive"]):
        risk = "INJURY_RISK"; confidence -= 35; exp_min *= 0.25
    elif any(x in stxt for x in ["day", "question", "probable", "doubt"]):
        risk = "INJURY_TAG"; confidence -= 15; exp_min *= 0.92
    confidence = int(clamp(confidence, 10, 96))
    return {
        "expected_minutes": float(clamp(exp_min, 4, 40)),
        "confidence": confidence,
        "risk": risk,
        "std": round(std, 2),
        "note": f"Weighted L3/L5/L10 minutes; last3={','.join(fmt(x,1) for x in last3)}",
    }


def usage_engine(logs: pd.DataFrame) -> Dict[str, Any]:
    if logs.empty:
        return {"fga": 6.0, "fta": 2.0, "usage_score": 45, "note": "Fallback usage"}
    fga = weighted_recent(logs.get("FGA", pd.Series(dtype=float)), None)
    fta = weighted_recent(logs.get("FTA", pd.Series(dtype=float)), None)
    tov = weighted_recent(logs.get("TOV", pd.Series(dtype=float)), 1.2)
    pts = weighted_recent(logs.get("PTS", pd.Series(dtype=float)), None)
    fga = fga if fga is not None else max((pts or 8.0) / 1.25, 4.0)
    fta = fta if fta is not None else 2.0
    usage_score = 45 + min(fga, 18) * 2.0 + min(fta, 7) * 1.1
    return {"fga": float(fga), "fta": float(fta), "tov": float(tov or 1.2), "usage_score": int(clamp(usage_score, 30, 95)), "note": "Weighted FGA/FTA/TOV"}


def build_team_recent_stats(games: pd.DataFrame, lookback_days: int = 21) -> Dict[str, Dict[str, float]]:
    # Uses completed scoreboard games available from selected dates plus recent scoreboard window fallback.
    today = california_now().date()
    date_list = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(0, lookback_days + 1)]
    all_games = []
    for ds in date_list:
        df = extract_games([ds])
        if not df.empty:
            all_games.append(df)
    df = pd.concat(all_games, ignore_index=True) if all_games else pd.DataFrame()
    stats: Dict[str, Dict[str, List[float]]] = {}
    if df.empty:
        return {}
    for _, g in df[df.get("completed", False).eq(True) if "completed" in df else []].iterrows():
        h, a = g["home_abbr"], g["away_abbr"]
        hs, as_ = safe_float(g.get("home_score")), safe_float(g.get("away_score"))
        if hs is None or as_ is None:
            continue
        for t, pf, pa in [(h, hs, as_), (a, as_, hs)]:
            stats.setdefault(t, {"pf": [], "pa": [], "pace_proxy": []})
            stats[t]["pf"].append(pf)
            stats[t]["pa"].append(pa)
            stats[t]["pace_proxy"].append(pf + pa)
    out = {}
    for t, vals in stats.items():
        out[t] = {
            "pf": float(np.mean(vals["pf"])) if vals["pf"] else 80.0,
            "pa": float(np.mean(vals["pa"])) if vals["pa"] else 80.0,
            "pace_proxy": float(np.mean(vals["pace_proxy"])) if vals["pace_proxy"] else 160.0,
            "games": len(vals["pf"]),
        }
    return out


def pace_factor(team_abbr: str, opp_abbr: str, team_stats: Dict[str, Dict[str, float]]) -> Tuple[float, str]:
    t = team_stats.get(clean_team_abbr(team_abbr), {})
    o = team_stats.get(clean_team_abbr(opp_abbr), {})
    tp = safe_float(t.get("pace_proxy"), 160.0) or 160.0
    op = safe_float(o.get("pace_proxy"), 160.0) or 160.0
    gp = (tp + op) / 2.0
    fac = clamp(gp / 160.0, 0.92, 1.08)
    return fac, f"Pace proxy {gp:.1f} vs 160 baseline"


def matchup_factor(opp_abbr: str, market: str, pos_bucket: str, team_stats: Dict[str, Dict[str, float]], dvp: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None) -> Tuple[float, str]:
    """Defense-vs-position matchup factor.

    Primary: recent ESPN boxscore-derived allowed production by Guard/Wing/Post.
    Fallback: opponent points-allowed proxy when DvP sample is too small.
    """
    opp_key = clean_team_abbr(opp_abbr)
    # Baseline per player appearance by position. Conservative to avoid overfitting public boxscores.
    baselines = {
        "Points": {"Guard": 10.8, "Wing": 9.6, "Post": 9.2},
        "Rebounds": {"Guard": 3.0, "Wing": 4.1, "Post": 5.7},
        "Assists": {"Guard": 3.0, "Wing": 1.9, "Post": 1.5},
    }
    if dvp and opp_key in dvp and pos_bucket in dvp[opp_key]:
        allowed = safe_float(dvp[opp_key][pos_bucket].get(market))
        n = safe_float(dvp[opp_key][pos_bucket].get(f"{market}_n"), 0.0) or 0.0
        base = baselines.get(market, {}).get(pos_bucket, 5.0)
        if allowed is not None and n >= 10 and base > 0:
            raw = allowed / base
            strength = clamp(n / 45.0, 0.35, 1.0)
            fac = 1 + ((raw - 1) * 0.55 * strength)
            return clamp(fac, 0.88, 1.13), f"DvP {opp_key} vs {pos_bucket}: {allowed:.2f} {market}/app (n={int(n)})"

    opp = team_stats.get(opp_key, {})
    pa = safe_float(opp.get("pa"), 80.0) or 80.0
    raw = pa / 80.0
    market_mult = {"Points": 0.80, "Rebounds": 0.40, "Assists": 0.50}.get(market, 0.60)
    role_hint = {"Guard": 1.035 if market == "Assists" else 1.00, "Wing": 1.00, "Post": 1.045 if market == "Rebounds" else 1.00}.get(pos_bucket, 1.00)
    fac = (1 + ((raw - 1) * market_mult)) * role_hint
    return clamp(fac, 0.91, 1.10), f"Fallback PA proxy {pa:.1f}; {pos_bucket} role"


def projection_for_market(logs: pd.DataFrame, market: str, exp_minutes: float, pace_fac: float, match_fac: float, learn_scale: float) -> Dict[str, Any]:
    stat = STAT_KEYS[market]
    if logs.empty or stat not in logs:
        per_min = {"Points": 0.36, "Rebounds": 0.16, "Assists": 0.10}[market]
        base = exp_minutes * per_min
        source = "Fallback per-minute"
    else:
        vals = pd.to_numeric(logs[stat], errors="coerce")
        mins = pd.to_numeric(logs["MIN"], errors="coerce").replace(0, np.nan)
        per_min_series = (vals / mins).replace([np.inf, -np.inf], np.nan).dropna()
        recent_pm = weighted_recent(per_min_series, None)
        stat_recent = weighted_recent(vals, None)
        if recent_pm is None and stat_recent is None:
            per_min = {"Points": 0.36, "Rebounds": 0.16, "Assists": 0.10}[market]
            base = exp_minutes * per_min
            source = "Fallback per-minute"
        else:
            by_rate = exp_minutes * (recent_pm or ((stat_recent or 0) / max(exp_minutes, 1)))
            by_stat = stat_recent if stat_recent is not None else by_rate
            base = 0.70 * by_rate + 0.30 * by_stat
            source = "Weighted per-minute + recent stat"
    proj = float(max(0, base * pace_fac * match_fac * learn_scale))
    return {"projection": proj, "source": source}


def volatility_for_market(logs: pd.DataFrame, market: str, exp_minutes: float, min_risk: str) -> float:
    stat = STAT_KEYS[market]
    base = {"Points": 4.2, "Rebounds": 2.4, "Assists": 1.8}[market]
    if not logs.empty and stat in logs:
        vals = pd.to_numeric(logs[stat], errors="coerce").dropna().head(10).tolist()
        if len(vals) >= 3:
            base = max(base * 0.65, float(np.std(vals)))
    if "VOLATILE" in min_risk or "INJURY" in min_risk:
        base *= 1.20
    if exp_minutes < 22:
        base *= 1.12
    return float(clamp(base, 0.8, {"Points": 9.0, "Rebounds": 5.5, "Assists": 4.8}[market]))


def run_prop_simulation(mean: float, sd: float, market: str, sims: int = SIMS) -> np.ndarray:
    # Negative binomial-ish via gamma-poisson blend for count-like stat with realistic tails.
    mean = max(0.05, float(mean))
    sd = max(0.3, float(sd))
    normal_part = np.random.normal(mean, sd, sims)
    poisson_part = np.random.poisson(max(mean, 0.05), sims)
    weight = {"Points": 0.72, "Rebounds": 0.55, "Assists": 0.50}[market]
    sim = (weight * normal_part) + ((1 - weight) * poisson_part)
    return np.clip(sim, 0, None)


def sim_probability(sims: np.ndarray, line: Optional[float], side: str) -> Optional[float]:
    if line is None:
        return None
    if side.upper() == "OVER":
        return float(np.mean(sims > line))
    return float(np.mean(sims < line))


def grade_from_prob(prob: Optional[float], data_score: int, edge: float) -> str:
    if prob is None:
        return "NO LINE"
    if data_score < MIN_DATA_SCORE:
        return "PASS"
    if prob >= 0.70 and edge >= 1.5:
        return "S"
    if prob >= 0.66:
        return "A"
    if prob >= 0.62:
        return "B"
    if prob >= 0.58:
        return "C"
    return "PASS"


def build_decision(proj: float, line: Optional[float], market: str, prob: Optional[float], data_score: int, source: str, minutes_conf: int = 0, minutes_risk: str = "") -> Tuple[str, str, str]:
    if line is None:
        return "NO UD LINE" if source == "NO REAL LINE" else "NO LINE", "NO LINE", "No verified real vendor line found"
    side = "OVER" if proj > line else "UNDER"
    edge = abs(proj - line)
    min_edge = MIN_BETTABLE_EDGE.get(market, 1.0)
    real_source = str(source or "").upper() not in ["NO REAL LINE", "MANUAL", ""]
    risk_txt = str(minutes_risk or "").upper()

    if not real_source:
        return f"PASS {side}", "PASS", "Not a verified real vendor line"
    if data_score < 88:
        return f"PASS {side}", "PASS", "Data score below 88 official gate"
    if minutes_conf < 72:
        return f"PASS {side}", "PASS", "Minutes confidence below safe gate"
    if any(x in risk_txt for x in ["OUT", "INJURY", "VOLATILE", "LOW_MINUTES", "MINUTES_LIMIT"]):
        return f"PASS {side}", "PASS", f"Minutes risk gate: {minutes_risk}"
    if side == "OVER" and minutes_conf < 78:
        return f"PASS {side}", "PASS", "Over reduced/pass due to non-elite minutes confidence"
    if prob is None or prob < MIN_BETTABLE_PROB:
        return f"PASS {side}", "PASS", "Probability below 63.5% official threshold"
    if edge < min_edge:
        return f"PASS {side}", "PASS", f"Edge {edge:.2f} below {min_edge:.2f} threshold"
    return f"✅ {side}", side, f"Official edge/prob/data/minutes gates passed via {source}"

# ============================================================
# LEARNING / CALIBRATION / CLV
# ============================================================
def learning_key(player_id: str, market: str) -> str:
    return f"{player_id}_{market}"


def load_learning() -> Dict[str, Any]:
    return load_json(LEARN_FILE, {})


def apply_learning(player_id: str, market: str, proj: float) -> Tuple[float, float]:
    data = load_learning()
    scale = safe_float(data.get(learning_key(player_id, market), 1.0), 1.0) or 1.0
    return proj * scale, scale


def update_learning(player_id: str, market: str, projected: float, actual: float) -> float:
    data = load_learning()
    key = learning_key(player_id, market)
    current = safe_float(data.get(key), 1.0) or 1.0
    if projected <= 0:
        return current
    # Require a few samples by shrinking update strongly.
    results = load_json(RESULT_LOG, [])
    samples = sum(1 for r in results if r.get("player_id") == player_id and r.get("market") == market and r.get("actual") is not None)
    lr = 0.015 if samples < 5 else 0.035
    err = clamp((actual - projected) / max(1.0, projected), -0.35, 0.35)
    new_scale = clamp(current * (1 + lr * err), 0.90, 1.10)
    data[key] = new_scale
    save_json(LEARN_FILE, data)
    return new_scale


def update_clv_snapshot(player_name: str, market: str, source: str, line: Optional[float]) -> Optional[float]:
    if line is None:
        return None
    data = load_json(CLV_FILE, {})
    today = california_now().strftime("%Y-%m-%d")
    key = f"{today}_{normalize_name(player_name)}_{market}_{source}"
    old = data.get(key)
    line = float(line)
    if not old:
        data[key] = {"player": player_name, "market": market, "source": source, "open_line": line, "latest_line": line, "last_updated": now_iso()}
        save_json(CLV_FILE, data)
        return 0.0
    open_line = safe_float(old.get("open_line"))
    old["latest_line"] = line
    old["last_updated"] = now_iso()
    data[key] = old
    save_json(CLV_FILE, data)
    return None if open_line is None else round(line - open_line, 2)


def calibration_profile() -> Dict[str, Any]:
    rows = load_json(RESULT_LOG, [])
    finished = [r for r in rows if r.get("actual") is not None and r.get("projection") is not None and r.get("graded_result") in ["WIN", "LOSS"]]
    if not finished:
        return {"samples": 0, "hit_rate": None, "mae": None, "bias": None, "quality": 50}
    errors = [safe_float(r.get("actual"), 0) - safe_float(r.get("projection"), 0) for r in finished]
    wins = [1 if r.get("graded_result") == "WIN" else 0 for r in finished]
    mae = float(np.mean([abs(e) for e in errors]))
    bias = float(np.mean(errors))
    hit = float(np.mean(wins))
    quality = int(clamp(48 + min(len(finished), 200) * 0.22 - mae * 3.2 - abs(bias) * 2.0, 0, 100))
    prof = {"samples": len(finished), "hit_rate": hit, "mae": round(mae, 3), "bias": round(bias, 3), "quality": quality, "updated_at": now_iso()}
    save_json(CALIBRATION_FILE, prof)
    return prof

# ============================================================
# BOARD BUILDER
# ============================================================
def build_player_pool(games: pd.DataFrame) -> pd.DataFrame:
    rosters = get_all_rosters()
    if rosters.empty or games.empty:
        return pd.DataFrame()
    slate_team_ids = set(games["home_id"].astype(str).tolist() + games["away_id"].astype(str).tolist())
    pool = rosters[rosters["team_id"].astype(str).isin(slate_team_ids)].copy()
    game_rows = []
    for _, g in games.iterrows():
        game_rows.append({"team_id": str(g["home_id"]), "team_abbr": g["home_abbr"], "opp_abbr": g["away_abbr"], "matchup": g["matchup"], "home": True, "event_id": g["event_id"], "game_time": g["game_time"]})
        game_rows.append({"team_id": str(g["away_id"]), "team_abbr": g["away_abbr"], "opp_abbr": g["home_abbr"], "matchup": g["matchup"], "home": False, "event_id": g["event_id"], "game_time": g["game_time"]})
    gm = pd.DataFrame(game_rows)
    pool = pool.merge(gm, on="team_id", how="left")
    return pool.dropna(subset=["event_id"])


def build_prop_board(games: pd.DataFrame, markets: List[str], line_source_pref: str, allow_manual: bool, manual_lines: pd.DataFrame, min_minutes: float, injury_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    pool = build_player_pool(games)
    lines = fetch_all_prop_lines()
    team_stats = build_team_recent_stats(games)
    dvp = build_defense_vs_position()
    injury_df = sanitize_injury_controls(injury_df if injury_df is not None else pd.DataFrame())
    rows = []
    if pool.empty:
        return pd.DataFrame()

    for _, p in pool.iterrows():
        player_id = str(p.get("player_id") or "")
        player = p.get("player")
        if not player_id or not player:
            continue
        logs = get_player_gamelog(player_id)
        min_model = minutes_engine(logs, str(p.get("status") or ""))
        exp_min = min_model["expected_minutes"]
        exp_min, manual_injury_risk, injury_penalty, injury_note = apply_player_injury_adjustment(player, p.get("team_abbr"), exp_min, injury_df)
        if manual_injury_risk != "ACTIVE":
            min_model["risk"] = manual_injury_risk
            min_model["confidence"] = int(clamp(min_model.get("confidence", 50) - injury_penalty, 0, 96))
            min_model["note"] = f"{min_model.get('note','')}; {injury_note}"
        if exp_min < min_minutes:
            continue
        use = usage_engine(logs)
        ripple = team_injury_ripple(p.get("team_abbr"), injury_df)
        pos_bucket = position_bucket(p.get("position"))
        pace_fac, pace_note = pace_factor(p.get("team_abbr"), p.get("opp_abbr"), team_stats)
        for market in markets:
            match_fac, match_note = matchup_factor(p.get("opp_abbr"), market, pos_bucket, team_stats, dvp)
            base_proj = projection_for_market(logs, market, exp_min, pace_fac, match_fac, 1.0)
            if ripple.get("usage_boost", 1.0) > 1.0 and manual_injury_risk != "OUT_MANUAL":
                base_proj["projection"] *= ripple.get("usage_boost", 1.0)
                base_proj["source"] += f" + injury ripple usage x{ripple.get('usage_boost', 1.0):.3f}"
            proj, learn_scale = apply_learning(player_id, market, base_proj["projection"])
            sd = volatility_for_market(logs, market, exp_min, min_model["risk"])
            sims = run_prop_simulation(proj, sd, market)
            p10, median, p90 = np.percentile(sims, [10, 50, 90])

            line_row = best_line_for_player(player, market, lines, preferred=line_source_pref)
            line = None
            source = "NO REAL LINE"
            price = DEFAULT_ODDS
            if line_row:
                line = safe_float(line_row.get("Line"))
                source = str(line_row.get("Source"))
                price = safe_float(line_row.get("Price"), DEFAULT_ODDS) or DEFAULT_ODDS
            elif allow_manual and not manual_lines.empty:
                ml = manual_lines[(manual_lines["Player"].apply(lambda x: name_score(player, x) >= 0.90)) & (manual_lines["Market"].eq(market))]
                if not ml.empty:
                    line = safe_float(ml.iloc[0]["Line"])
                    source = "MANUAL"
                    price = safe_float(ml.iloc[0].get("Price"), DEFAULT_ODDS) or DEFAULT_ODDS

            side = "OVER" if line is not None and proj > line else "UNDER" if line is not None else "NO LINE"
            prob = sim_probability(sims, line, side) if line is not None else None
            # Reduce fragile overs before the official filter sees them.
            if prob is not None and side == "OVER" and ("VOLATILE" in str(min_model["risk"]).upper() or min_model["confidence"] < 78):
                prob = max(0.0, prob - 0.035)
            edge = abs(proj - line) if line is not None else None
            ev = expected_value(prob, price) if prob is not None else None
            kelly = min(kelly_fraction(prob, price), MAX_RECOMMENDED_KELLY) if prob is not None else 0.0
            data_score = int(clamp(40 + min_model["confidence"] * 0.42 + use["usage_score"] * 0.25 + (10 if len(logs) >= 5 else 0) + (7 if source not in ["NO REAL LINE", "MANUAL"] else 0), 0, 100))
            decision, official_side, reason = build_decision(proj, line, market, prob, data_score, source, min_model["confidence"], min_model["risk"])
            tier = grade_from_prob(prob, data_score, edge or 0)
            clv = update_clv_snapshot(player, market, source, line) if line is not None and source != "MANUAL" else None

            rows.append({
                "Player": player,
                "Player ID": player_id,
                "Team": p.get("team_abbr"),
                "Opponent": p.get("opp_abbr"),
                "Matchup": p.get("matchup"),
                "Market": market,
                "Line": line,
                "Line Source": source,
                "Price": price,
                "Projection": round(proj, 2),
                "Pick": decision,
                "Official Side": official_side,
                "Tier": tier,
                "Prob %": None if prob is None else round(prob * 100, 1),
                "Edge": None if edge is None else round(edge, 2),
                "EV": None if ev is None else round(ev, 3),
                "Kelly": round(kelly, 4),
                "Floor": round(float(p10), 2),
                "Median": round(float(median), 2),
                "Ceiling": round(float(p90), 2),
                "Expected Min": round(exp_min, 1),
                "Minutes Risk": min_model["risk"],
                "Minutes Conf": min_model["confidence"],
                "Usage Score": use["usage_score"],
                "Pace Factor": round(pace_fac, 3),
                "Matchup Factor": round(match_fac, 3),
                "Position": p.get("position"),
                "Role": pos_bucket,
                "Data Score": data_score,
                "Learn Scale": round(learn_scale, 3),
                "CLV Δ": clv,
                "Reason": reason,
                "Pace Note": pace_note,
                "Matchup Note": match_note,
                "Injury Note": injury_note,
                "Team Injury Ripple": f"OUT {int(ripple.get('out_count',0))} | Q {int(ripple.get('q_count',0))} | LIMIT {int(ripple.get('limit_count',0))} | usage x{ripple.get('usage_boost',1.0):.3f}",
                "Minutes Note": min_model["note"],
                "Projection Source": base_proj["source"],
                "Game Time": p.get("game_time"),
                "Event ID": p.get("event_id"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    sort_cols = ["Tier", "Prob %", "Edge", "Data Score"]
    tier_order = {"S": 5, "A": 4, "B": 3, "C": 2, "PASS": 1, "NO LINE": 0}
    df["_tier_sort"] = df["Tier"].map(tier_order).fillna(0)
    df = df.sort_values(["_tier_sort", "Prob %", "Edge", "Data Score"], ascending=[False, False, False, False]).drop(columns=["_tier_sort"])
    return df

# ============================================================
# MONEYLINE ENGINE
# ============================================================
def odds_api_moneylines() -> pd.DataFrame:
    if not ODDS_API_KEY:
        return pd.DataFrame()
    try:
        data = safe_get_json(f"{ODDS_API_BASE}/sports/basketball_wnba/odds", params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
        }, timeout=18) or []
        rows = []
        for game in data:
            home = game.get("home_team")
            away = game.get("away_team")
            for book in game.get("bookmakers", []) or []:
                for market in book.get("markets", []) or []:
                    if market.get("key") != "h2h":
                        continue
                    for out in market.get("outcomes", []) or []:
                        rows.append({
                            "Game": f"{away} @ {home}",
                            "Team": out.get("name"),
                            "Price": safe_float(out.get("price")),
                            "Book": book.get("title"),
                        })
        return pd.DataFrame(rows)
    except Exception as e:
        log_source_request("OddsAPI", "ERROR", str(e))
        return pd.DataFrame()


def team_rating(abbr: str, team_stats: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    s = team_stats.get(clean_team_abbr(abbr), {})
    pf = safe_float(s.get("pf"), 80.0) or 80.0
    pa = safe_float(s.get("pa"), 80.0) or 80.0
    pace = safe_float(s.get("pace_proxy"), 160.0) or 160.0
    games = safe_float(s.get("games"), 0.0) or 0.0
    net = pf - pa
    # Shrink if low sample.
    shrink = games / (games + 5.0)
    return {"pf": pf, "pa": pa, "net": net * shrink, "pace": pace, "games": games}


def build_moneyline_board(games: pd.DataFrame, injury_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if games.empty:
        return pd.DataFrame()
    team_stats = build_team_recent_stats(games)
    injury_df = sanitize_injury_controls(injury_df if injury_df is not None else pd.DataFrame())
    odds = odds_api_moneylines()
    rows = []
    for _, g in games.iterrows():
        h = clean_team_abbr(g["home_abbr"]); a = clean_team_abbr(g["away_abbr"])
        hr = team_rating(h, team_stats); ar = team_rating(a, team_stats)
        h_inj = team_injury_ripple(h, injury_df); a_inj = team_injury_ripple(a, injury_df)
        home_adv = 2.1 if not g.get("neutral") else 0.0
        expected_margin = (hr["net"] - ar["net"]) + home_adv + h_inj.get("ml_adj", 0.0) - a_inj.get("ml_adj", 0.0)
        total_base = ((hr["pf"] + ar["pf"] + hr["pa"] + ar["pa"]) / 2.0)
        pace = ((hr["pace"] + ar["pace"]) / 2.0) / 160.0
        total_base *= clamp(pace, 0.94, 1.06)
        margins = np.random.normal(expected_margin, 10.5, ML_SIMS)
        home_win = float(np.mean(margins > 0))
        away_win = 1 - home_win
        home_score = total_base / 2 + expected_margin / 2
        away_score = total_base / 2 - expected_margin / 2

        for team_name, abbr, win_prob, model_margin in [
            (g["home_team"], h, home_win, expected_margin),
            (g["away_team"], a, away_win, -expected_margin),
        ]:
            price = None; book = None; book_prob = None; edge = None
            if not odds.empty:
                tmp = odds.copy()
                tmp["score"] = tmp["Team"].apply(lambda x: max(name_score(team_name, x), name_score(abbr, x)))
                tmp = tmp[tmp["score"] >= 0.65].sort_values("score", ascending=False)
                if not tmp.empty:
                    price = safe_float(tmp.iloc[0]["Price"]); book = tmp.iloc[0]["Book"]
                    book_prob = american_to_implied(price)
                    edge = win_prob - book_prob if book_prob is not None else None
            tier = "NO ODDS"
            decision = "NO ODDS"
            if edge is not None:
                if edge >= 0.08 and win_prob >= 0.58:
                    tier = "A"; decision = "✅ ML"
                elif edge >= 0.05 and win_prob >= 0.55:
                    tier = "B"; decision = "LEAN ML"
                elif edge >= 0.025:
                    tier = "C"; decision = "PASS ML LEAN"
                else:
                    tier = "PASS"; decision = "PASS"
            rows.append({
                "Game": g["matchup"],
                "Team": abbr,
                "Team Name": team_name,
                "Model Win %": round(win_prob * 100, 1),
                "Book Win %": None if book_prob is None else round(book_prob * 100, 1),
                "ML Price": price,
                "Book": book,
                "Edge %": None if edge is None else round(edge * 100, 1),
                "Decision": decision,
                "Tier": tier,
                "Model Margin": round(model_margin, 1),
                "Projected Score": round(home_score, 1) if abbr == h else round(away_score, 1),
                "Recent Net": round(hr["net"], 1) if abbr == h else round(ar["net"], 1),
                "Injury ML Adj": round(h_inj.get("ml_adj", 0.0), 2) if abbr == h else round(a_inj.get("ml_adj", 0.0), 2),
                "Games In Sample": int(hr["games"] if abbr == h else ar["games"]),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    tier_order = {"A": 4, "B": 3, "C": 2, "PASS": 1, "NO ODDS": 0}
    df["_tier"] = df["Tier"].map(tier_order).fillna(0)
    return df.sort_values(["_tier", "Edge %", "Model Win %"], ascending=[False, False, False]).drop(columns=["_tier"])

# ============================================================
# SAVE / GRADE WORKFLOW
# ============================================================
def save_official_picks(board: pd.DataFrame, ml_board: pd.DataFrame) -> int:
    rows = load_json(PICK_LOG, [])
    today = california_now().strftime("%Y-%m-%d")
    count = 0
    if not board.empty:
        official = board[board["Pick"].astype(str).str.startswith("✅")].copy()
        for _, r in official.iterrows():
            item = r.to_dict()
            item.update({"saved_at": now_iso(), "date": today, "type": "PROP", "pick_id": f"{today}_{r['Player ID']}_{r['Market']}_{r['Line Source']}"})
            if item["pick_id"] not in [x.get("pick_id") for x in rows]:
                rows.append(item); count += 1
    if not ml_board.empty:
        official_ml = ml_board[ml_board["Decision"].astype(str).str.startswith("✅")].copy()
        for _, r in official_ml.iterrows():
            item = r.to_dict()
            item.update({"saved_at": now_iso(), "date": today, "type": "MONEYLINE", "pick_id": f"{today}_ML_{r['Team']}_{r['Game']}"})
            if item["pick_id"] not in [x.get("pick_id") for x in rows]:
                rows.append(item); count += 1
    save_json(PICK_LOG, rows[-5000:])
    return count


def grade_saved_props() -> int:
    saved = load_json(PICK_LOG, [])
    results = load_json(RESULT_LOG, [])
    existing = set(r.get("pick_id") for r in results)
    graded = 0
    for p in saved:
        if p.get("type") != "PROP" or p.get("pick_id") in existing:
            continue
        event_id = str(p.get("Event ID") or "")
        if not event_id:
            continue
        box = boxscore_player_rows(event_id)
        if box.empty:
            continue
        match = box.copy()
        match["score"] = match["player"].apply(lambda x: name_score(p.get("Player"), x))
        match = match[match["score"] >= 0.88].sort_values("score", ascending=False)
        if match.empty:
            continue
        row = match.iloc[0]
        actual = safe_float(row.get(STAT_KEYS.get(p.get("Market"), "PTS")))
        line = safe_float(p.get("Line"))
        side = str(p.get("Official Side") or "")
        if actual is None or line is None or side not in ["OVER", "UNDER"]:
            continue
        win = actual > line if side == "OVER" else actual < line
        res = dict(p)
        res.update({"actual": actual, "graded_at": now_iso(), "graded_result": "WIN" if win else "LOSS", "win": bool(win)})
        results.append(res)
        update_learning(str(p.get("Player ID")), str(p.get("Market")), safe_float(p.get("Projection"), 0) or 0, actual)
        graded += 1
    save_json(RESULT_LOG, results[-5000:])
    return graded

# ============================================================
# DISPLAY HELPERS
# ============================================================
def render_header() -> None:
    st.markdown(f"""
    <div class='hero-panel'>
      <div class='big-title'>WNBA Elite Prop + Moneyline Engine</div>
      <div class='sub-title'>Points • Rebounds • Assists • Moneyline | Real WNBA stats + real lines when available | {APP_VERSION}</div>
      <div style='margin-top:10px'>
        <span class='badge good-badge'>Minutes Engine</span>
        <span class='badge'>Usage Engine</span>
        <span class='badge'>Pace Engine</span>
        <span class='badge'>Monte Carlo {SIMS:,}</span>
        <span class='badge'>CLV + Learning</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpis(board: pd.DataFrame, ml_board: pd.DataFrame, games: pd.DataFrame) -> None:
    props = 0 if board.empty else len(board)
    official = 0 if board.empty else int(board["Pick"].astype(str).str.startswith("✅").sum())
    no_line = 0 if board.empty else int(board["Line Source"].eq("NO REAL LINE").sum())
    ml_edges = 0 if ml_board.empty else int(ml_board["Decision"].astype(str).str.startswith("✅").sum())
    prof = calibration_profile()
    st.markdown(f"""
    <div class='kpi-strip'>
      <div class='kpi-box'><div class='kpi-label'>Games</div><div class='kpi-value'>{len(games)}</div><div class='kpi-sub'>Current slate</div></div>
      <div class='kpi-box'><div class='kpi-label'>Prop Rows</div><div class='kpi-value'>{props}</div><div class='kpi-sub'>P/R/A board</div></div>
      <div class='kpi-box'><div class='kpi-label'>Official Props</div><div class='kpi-value green'>{official}</div><div class='kpi-sub'>Passed hard gates</div></div>
      <div class='kpi-box'><div class='kpi-label'>No Real Line</div><div class='kpi-value orange'>{no_line}</div><div class='kpi-sub'>Projection only</div></div>
      <div class='kpi-box'><div class='kpi-label'>ML Edges</div><div class='kpi-value green'>{ml_edges}</div><div class='kpi-sub'>Odds API required</div></div>
      <div class='kpi-box'><div class='kpi-label'>Learning</div><div class='kpi-value'>{prof.get('samples',0)}</div><div class='kpi-sub'>Graded samples</div></div>
    </div>
    """, unsafe_allow_html=True)


def board_view(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Player", "Team", "Matchup", "Market", "Line", "Line Source", "Projection", "Pick", "Tier", "Prob %", "Edge", "Expected Min", "Minutes Risk", "Data Score", "Floor", "Median", "Ceiling", "Reason"]
    return df[[c for c in cols if c in df.columns]].copy() if not df.empty else df


def render_player_cards(df: pd.DataFrame, max_cards: int = 20) -> None:
    if df.empty:
        st.info("No rows to show.")
        return
    for _, r in df.head(max_cards).iterrows():
        badge_class = "good-badge" if str(r.get("Pick", "")).startswith("✅") else "yellow-badge" if "PASS" in str(r.get("Pick", "")) else "badge"
        st.markdown(f"""
        <div class='pick-card'>
          <div class='player-name'>{html.escape(str(r.get('Player')))} — {html.escape(str(r.get('Market')))}</div>
          <div class='small-muted'>{html.escape(str(r.get('Team')))} vs {html.escape(str(r.get('Opponent')))} | {html.escape(str(r.get('Matchup')))}</div>
          <div style='margin-top:8px'>
            <span class='badge {badge_class}'>{html.escape(str(r.get('Pick')))}</span>
            <span class='badge'>Line: {fmt(r.get('Line'),1)} {html.escape(str(r.get('Line Source')))}</span>
            <span class='badge'>Proj: {fmt(r.get('Projection'),2)}</span>
            <span class='badge'>Prob: {fmt(r.get('Prob %'),1)}%</span>
            <span class='badge'>Tier: {html.escape(str(r.get('Tier')))}</span>
          </div>
          <div class='hr-soft'></div>
          <div class='small-muted'>Floor {fmt(r.get('Floor'),1)} | Median {fmt(r.get('Median'),1)} | Ceiling {fmt(r.get('Ceiling'),1)} | Min {fmt(r.get('Expected Min'),1)} | Data {r.get('Data Score')}</div>
          <div class='small-muted'>Reason: {html.escape(str(r.get('Reason')))}</div>
          <div class='small-muted'>Pace: {html.escape(str(r.get('Pace Note')))} | Matchup: {html.escape(str(r.get('Matchup Note')))}</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# MAIN APP
# ============================================================
def main() -> None:
    render_header()

    with st.sidebar:
        st.header("Controls")
        day_mode = st.selectbox("Slate", ["Today", "Tomorrow", "Today + Tomorrow"], index=0)
        markets = st.multiselect("Markets", MARKETS, default=MARKETS)
        line_source_pref = st.selectbox("Preferred Line Source", ["Underdog", "PrizePicks"], index=0)
        min_minutes = st.slider("Minimum Expected Minutes", 0.0, 32.0, 14.0, 1.0)
        allow_manual = st.checkbox("Allow manual lines if no real line", value=False)
        st.caption("Manual lines are labeled MANUAL and are not treated as real vendor lines.")
        uploaded_manual = st.file_uploader("Optional manual lines CSV: Player,Market,Line,Price", type=["csv"])
        refresh = st.button("Refresh Board", type="primary")
        st.divider()
        if st.button("Save Official Plays"):
            st.session_state["save_requested"] = True
        if st.button("Grade Completed Saved Props"):
            st.session_state["grade_requested"] = True

    manual_lines = pd.DataFrame()
    if uploaded_manual is not None:
        try:
            manual_lines = pd.read_csv(uploaded_manual)
        except Exception as e:
            st.sidebar.error(f"Manual CSV error: {e}")

    dates = target_dates(day_mode)
    games = extract_games(dates)

    if games.empty:
        st.warning("No WNBA games found for this slate from ESPN. Try Today + Tomorrow or check the schedule date.")
        st.stop()

    with st.sidebar:
        st.divider()
        st.subheader("Manual Injury Ripple")
        st.caption("Use this to mark OUT / QUESTIONABLE / MINUTES LIMIT. Team ML Adj is optional; negative hurts that team, positive boosts it.")
        saved_inj = pd.DataFrame(load_json(INJURY_CONTROL_FILE, []))
        if saved_inj.empty:
            saved_inj = pd.DataFrame([{"Player": "", "Team": "", "Status": "ACTIVE", "Minutes Limit": None, "Team ML Adj": 0.0, "Notes": ""}])
        injury_controls = st.data_editor(
            saved_inj,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["ACTIVE", "OUT", "QUESTIONABLE", "MINUTES LIMIT"]),
                "Minutes Limit": st.column_config.NumberColumn("Minutes Limit", min_value=0.0, max_value=40.0, step=1.0),
                "Team ML Adj": st.column_config.NumberColumn("Team ML Adj", step=0.5),
            },
            key="injury_controls_editor",
        )
        if st.button("Save Injury Controls"):
            clean_inj = sanitize_injury_controls(injury_controls)
            save_json(INJURY_CONTROL_FILE, clean_inj.to_dict(orient="records"))
            st.success("Injury controls saved.")
    injury_controls = sanitize_injury_controls(injury_controls)

    with st.expander("Slate Games", expanded=True):
        st.dataframe(games[["date", "matchup", "game_time", "status", "venue"]], use_container_width=True, hide_index=True)

    with st.spinner("Building WNBA prop board with ESPN stats, real prop lines, pace, minutes, and simulations..."):
        board = build_prop_board(games, markets, line_source_pref, allow_manual, manual_lines, min_minutes, injury_controls)
        ml_board = build_moneyline_board(games, injury_controls)

    if st.session_state.get("save_requested"):
        n = save_official_picks(board, ml_board)
        st.success(f"Saved {n} official plays.")
        st.session_state["save_requested"] = False

    if st.session_state.get("grade_requested"):
        n = grade_saved_props()
        st.success(f"Graded {n} completed prop plays.")
        st.session_state["grade_requested"] = False

    render_kpis(board, ml_board, games)

    tabs = st.tabs(["Best Bets", "Main Board", "Points", "Rebounds", "Assists", "Moneyline", "Player Cards", "Saved/Graded", "Diagnostics"])

    with tabs[0]:
        st.markdown("<div class='section-title-pro'>Best Prop Plays</div>", unsafe_allow_html=True)
        if board.empty:
            st.info("No prop board rows built.")
        else:
            best = board[board["Pick"].astype(str).str.startswith("✅")].copy()
            if best.empty:
                st.warning("No official prop plays passed the hard gates. Showing top leans instead.")
                best = board[board["Line"].notna()].head(12)
            st.dataframe(board_view(best), use_container_width=True, hide_index=True)
            render_player_cards(best, 8)
        st.markdown("<div class='section-title-pro'>Best Moneylines</div>", unsafe_allow_html=True)
        if ml_board.empty:
            st.info("No moneyline board available.")
        else:
            st.dataframe(ml_board.head(12), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.dataframe(board_view(board), use_container_width=True, hide_index=True)
        if not board.empty:
            csv = board.to_csv(index=False).encode("utf-8")
            st.download_button("Download Full Prop Board CSV", csv, "wnba_prop_board.csv", "text/csv")

    for i, market in enumerate(["Points", "Rebounds", "Assists"], start=2):
        with tabs[i]:
            sub = board[board["Market"].eq(market)] if not board.empty else pd.DataFrame()
            st.dataframe(board_view(sub), use_container_width=True, hide_index=True)
            render_player_cards(sub, 10)

    with tabs[5]:
        st.markdown("Moneyline model uses real recent ESPN scores/team results. Sportsbook odds require ODDS_API_KEY for live market edge.")
        st.dataframe(ml_board, use_container_width=True, hide_index=True)
        if not ml_board.empty:
            st.download_button("Download Moneyline CSV", ml_board.to_csv(index=False).encode("utf-8"), "wnba_moneyline_board.csv", "text/csv")

    with tabs[6]:
        player_search = st.text_input("Search player")
        sub = board.copy()
        if player_search and not sub.empty:
            sub["_s"] = sub["Player"].apply(lambda x: name_score(player_search, x))
            sub = sub[sub["_s"] >= 0.50].sort_values("_s", ascending=False).drop(columns=["_s"])
        render_player_cards(sub, 25)

    with tabs[7]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Saved Picks")
            saved = pd.DataFrame(load_json(PICK_LOG, []))
            st.dataframe(saved.tail(200), use_container_width=True, hide_index=True)
        with c2:
            st.subheader("Graded Results")
            results = pd.DataFrame(load_json(RESULT_LOG, []))
            st.dataframe(results.tail(200), use_container_width=True, hide_index=True)
        prof = calibration_profile()
        st.json(prof)

    with tabs[8]:
        st.subheader("Line Feed Status")
        lines = fetch_all_prop_lines()
        st.write(f"Real prop lines found: {len(lines)}")
        st.dataframe(lines.head(200), use_container_width=True, hide_index=True)

        st.subheader("Underdog Debug — Every Pulled Candidate")
        ud_debug = pd.DataFrame(load_json(UNDERDOG_DEBUG_FILE, []))
        if ud_debug.empty:
            st.info("No Underdog debug rows stored yet. Refresh the board to pull UD.")
        else:
            st.dataframe(ud_debug.tail(500), use_container_width=True, hide_index=True)

        st.subheader("Manual Injury Controls Active")
        st.dataframe(injury_controls, use_container_width=True, hide_index=True)

        st.subheader("Defense vs Position Sample")
        dvp = build_defense_vs_position()
        flat_dvp = []
        for team, by_pos in dvp.items():
            for role, mkts in by_pos.items():
                row = {"Opponent": team, "Role": role}
                row.update(mkts)
                flat_dvp.append(row)
        st.dataframe(pd.DataFrame(flat_dvp).head(300), use_container_width=True, hide_index=True)
        st.subheader("Request Log")
        req = pd.DataFrame(load_json(REQUEST_LOG_FILE, []))
        st.dataframe(req.tail(200), use_container_width=True, hide_index=True)
        st.subheader("Team Stats Proxy")
        st.json(build_team_recent_stats(games))


if __name__ == "__main__":
    main()
