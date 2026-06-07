from datetime import date, timedelta
import pandas as pd
from app import atg
from app import db
from app.models.models import (
    DriverOverallStats, HorseAnalysis, HorseOverallStats,
    HorseTrackStats, RaceAnalysis, UpcomingGameResponse,
)

class AtgFetchError(Exception):
    def __init__(self, day: str, cause: Exception):
        self.day = day
        self.cause = cause
        super().__init__(f"ATG fetch failed for {day}: {cause}")


class NoDatabaseDataError(Exception):
    pass


class UpcomingGameNotFoundError(Exception):
    pass


def fetch_and_store(days: int, dataset: str) -> pd.DataFrame:
    yesterday = date.today() - timedelta(days=1)
    day_strs = [(yesterday - timedelta(days=i)).isoformat() for i in range(days)]
    existing = db.has_dates(day_strs)

    for day in day_strs:
        if day in existing:
            continue
        try:
            df_day = atg.fetch_day_df(day)
        except Exception as e:
            raise AtgFetchError(day, e)
        if not df_day.empty:
            db.save_starters(df_day)

    df = db.load_all()
    if df.empty:
        raise NoDatabaseDataError()

    if dataset == "horses":
        df = atg.build_horse_stats(df)

    return df


def get_count() -> int:
    return db.count_starters()


def get_dates() -> list[str]:
    return db.stored_dates()


def get_starters(limit: int) -> list[dict]:
    return db.load_starters(limit)


def get_stats() -> dict:
    df = db.load_all()
    if df.empty:
        raise NoDatabaseDataError()
    return df.describe().to_dict()


def get_preview(n: int) -> list[dict]:
    df = db.load_all()
    if df.empty:
        raise NoDatabaseDataError()
    return df.head(n).to_dict(orient="records")


_GAME_TYPE_ALIASES = {"V85": "V75"}


def analyze_upcoming(game_type: str, date_str: str) -> UpcomingGameResponse:

    api_type = _GAME_TYPE_ALIASES.get(game_type.upper(), game_type.upper())

    try:
        entries = atg.fetch_upcoming_starts(api_type, date_str)
    except Exception as e:
        raise AtgFetchError(date_str, e)

    if not entries:
        raise UpcomingGameNotFoundError()

    horse_ids = [e["horse_id"] for e in entries if e["horse_id"]]
    driver_ids = [e["driver_id"] for e in entries if e["driver_id"]]

    overall_stats = db.load_horse_stats(horse_ids)

    track_stats: dict[str, dict[int, dict]] = {}
    for track in {e["track"] for e in entries if e["track"]}:
        track_horse_ids = [e["horse_id"] for e in entries if e["track"] == track and e["horse_id"]]
        track_stats[track] = db.load_horse_stats(track_horse_ids, track=track)

    driver_stats = db.load_driver_stats(driver_ids)

    races_map: dict[int, list[dict]] = {}
    for e in entries:
        rn = e["race_number"]
        races_map.setdefault(rn, []).append(e)

    races: list[RaceAnalysis] = []
    horses_with_history = 0

    for race_number in sorted(races_map):
        race_entries = races_map[race_number]
        track_name = race_entries[0]["track"]
        starters: list[HorseAnalysis] = []

        for e in race_entries:
            hid = e["horse_id"]
            did = e["driver_id"]

            h_overall = None
            if hid and hid in overall_stats:
                horses_with_history += 1
                s = overall_stats[hid]
                h_overall = HorseOverallStats(**{k: v for k, v in s.items() if k != "name"})

            h_track = None
            if hid and track_name and track_name in track_stats:
                ts = track_stats[track_name].get(hid)
                if ts:
                    h_track = HorseTrackStats(track=track_name, **{k: v for k, v in ts.items() if k != "name"})

            d_stats = None
            if did and did in driver_stats:
                d_stats = DriverOverallStats(**driver_stats[did])

            starters.append(HorseAnalysis(
                post_position=e["post_position"],
                horse_name=e["horse_name"],
                horse_age=e["horse_age"],
                driver_name=e["driver_name"],
                overall=h_overall,
                track=h_track,
                driver=d_stats,
            ))

        races.append(RaceAnalysis(
            race_number=race_number,
            track=track_name,
            distance_m=race_entries[0]["distance_m"],
            starters=starters,
        ))

    return UpcomingGameResponse(
        game_type=game_type.upper(),
        date=date_str,
        races=races,
        total_horses=len(entries),
        horses_with_history=horses_with_history,
    )
