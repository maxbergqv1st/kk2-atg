from datetime import date, timedelta

import pandas as pd

from app import atg
from app import db
class AtgFetchError(Exception):
    def __init__(self, day: str, cause: Exception):
        self.day = day
        self.cause = cause
        super().__init__(f"ATG fetch failed for {day}: {cause}")


class NoDatabaseDataError(Exception):
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
