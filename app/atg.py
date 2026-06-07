import time

import numpy as np
import pandas as pd
import requests
from requests.exceptions import ConnectionError, ReadTimeout, Timeout

BASE = "https://www.atg.se/services/racinginfo/v1/api"
GAME_TYPES = {"V75": "V85", "V85": "V85", "V64": "V64", "V86": "V86"}
CHAR_MAP = str.maketrans("åäæÅÄÆøöØÖ", "aaaAAAooOO")


def _fetch(url: str, max_retries: int = 3, timeout: int = 60) -> dict:
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (Timeout, ReadTimeout, ConnectionError):
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def _normalize(name: str | None) -> str | None:
    return name.translate(CHAR_MAP) if name else name


def _race_time_sec(t: dict | None, distance_m: float | None) -> float | None:
    if not t or not distance_m:
        return None
    per_km = t.get("minutes", 0) * 60 + t.get("seconds", 0) + t.get("tenths", 0) / 10
    return per_km * (distance_m / 1000)


def _extract_rows(date_str: str, calendar: dict) -> list[dict]:
    rows: list[dict] = []
    for game_type, game_list in calendar.get("games", {}).items():
        if game_type not in GAME_TYPES:
            continue
        for stub in game_list:
            game = _fetch(f"{BASE}/games/{stub['id']}")
            for race in game.get("races", []):
                rd = _fetch(f"{BASE}/races/{race['id']}")
                distance_m = rd.get("distance")
                for start in rd.get("starts", []):
                    horse = start.get("horse", {})
                    driver = start.get("driver", {})
                    result = start.get("result", {}) or {}
                    scratched = start.get("scratched", False)
                    rows.append({
                        "date": date_str,
                        "game_type": game_type,
                        "track": (rd.get("track") or {}).get("name"),
                        "distance_m": distance_m,
                        "horse_id": horse.get("id"),
                        "horse_name": _normalize(horse.get("name")),
                        "horse_age": horse.get("age"),
                        "driver_id": driver.get("id"),
                        "driver_name": _normalize(
                            driver.get("firstName", "") + " " + driver.get("lastName", "")
                        ),
                        "finish_position": np.nan if scratched else result.get("finishOrder"),
                        "odds": np.nan if scratched else result.get("finalOdds"),
                        "race_time_sec": np.nan if scratched else _race_time_sec(result.get("kmTime"), distance_m),
                        "won": 0 if scratched else int(result.get("finishOrder") == 1),
                        "scratched": scratched,
                    })
    return rows


def fetch_day_df(date_str: str) -> pd.DataFrame:
    """Hämtar en dags starter från ATG. `date` behålls som ISO-sträng för DB-dedup."""
    calendar = _fetch(f"{BASE}/calendar/day/{date_str}")
    rows = _extract_rows(date_str, calendar)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["distance_m", "odds", "finish_position", "horse_age"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch_upcoming_starts(game_type: str, date_str: str) -> list[dict]:
    """Hämtar kommande starter (utan resultat) för en speltyp och datum."""
    calendar = _fetch(f"{BASE}/calendar/day/{date_str}")
    gt_upper = game_type.upper()
    game_stubs = calendar.get("games", {}).get(gt_upper, [])
    if not game_stubs:
        return []

    entries: list[dict] = []
    for stub in game_stubs:
        game = _fetch(f"{BASE}/games/{stub['id']}")
        for race in game.get("races", []):
            rd = _fetch(f"{BASE}/races/{race['id']}")
            track_name = (rd.get("track") or {}).get("name")
            distance_m = rd.get("distance")
            race_number = rd.get("number")
            for start in rd.get("starts", []):
                if start.get("scratched", False):
                    continue
                horse = start.get("horse", {})
                driver = start.get("driver", {})
                entries.append({
                    "race_number": race_number,
                    "track": track_name,
                    "distance_m": distance_m,
                    "post_position": start.get("number"),
                    "horse_id": horse.get("id"),
                    "horse_name": _normalize(horse.get("name")),
                    "horse_age": horse.get("age"),
                    "driver_id": driver.get("id"),
                    "driver_name": _normalize(
                        driver.get("firstName", "") + " " + driver.get("lastName", "")
                    ),
                })
    return entries


def build_horse_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregerar starter till statistik per häst (motsv. horses.csv)."""
    active = df[~df["scratched"]].dropna(subset=["horse_id"])
    stats = active.groupby("horse_id").agg(
        name=("horse_name", "first"),
        starts=("won", "count"),
        wins=("won", "sum"),
        avg_odds=("odds", "mean"),
        avg_position=("finish_position", "mean"),
    ).reset_index()
    stats["win_pct"] = (stats["wins"] / stats["starts"] * 100).round(1)
    return stats.sort_values("starts", ascending=False)