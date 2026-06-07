import numpy as np
import pandas as pd
from sqlalchemy import func

from app.db.schema import SessionLocal, Starter


def _clean(record: dict) -> dict:
    out: dict = {}
    for key, value in record.items():
        if pd.isna(value):
            out[key] = None
        elif isinstance(value, np.integer):
            out[key] = int(value)
        elif isinstance(value, np.floating):
            out[key] = float(value)
        elif isinstance(value, np.bool_):
            out[key] = bool(value)
        else:
            out[key] = value
    return out

def save_starters(df: pd.DataFrame) -> None:
    objects = [Starter(**_clean(rec)) for rec in df.to_dict(orient="records")]
    with SessionLocal() as session:
        session.add_all(objects)
        session.commit()


def has_dates(date_strs: list[str]) -> set[str]:
    with SessionLocal() as session:
        rows = (
            session.query(Starter.date)
            .filter(Starter.date.in_(date_strs))
            .distinct()
            .all()
        )
        return {row[0] for row in rows}


def count_starters() -> int:
    with SessionLocal() as session:
        return session.query(Starter).count()


def stored_dates() -> list[str]:
    with SessionLocal() as session:
        rows = (
            session.query(Starter.date)
            .distinct()
            .order_by(Starter.date)
            .all()
        )
        return [row[0] for row in rows]


def load_starters(limit: int = 50) -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Starter).limit(limit).all()
        if not rows:
            return []
        columns = [c.name for c in Starter.__table__.columns if c.name != "id"]
        return [{col: getattr(row, col) for col in columns} for row in rows]


def load_all() -> pd.DataFrame:
    with SessionLocal() as session:
        rows = session.query(Starter).all()
        if not rows:
            return pd.DataFrame()
        columns = [c.name for c in Starter.__table__.columns]
        records = [{col: getattr(row, col) for col in columns} for row in rows]
    df = pd.DataFrame(records).drop(columns=["id"], errors="ignore")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def lookup_horse_id(name: str) -> int | None:
    with SessionLocal() as session:
        row = (
            session.query(Starter.horse_id)
            .filter(func.lower(Starter.horse_name) == name.lower(), Starter.horse_id.isnot(None))
            .order_by(Starter.date.desc())
            .first()
        )
        return row[0] if row else None


def lookup_driver_id(name: str) -> int | None:
    with SessionLocal() as session:
        row = (
            session.query(Starter.driver_id)
            .filter(func.lower(Starter.driver_name) == name.lower(), Starter.driver_id.isnot(None))
            .order_by(Starter.date.desc())
            .first()
        )
        return row[0] if row else None


def load_horse_stats(
    horse_ids: list[int] | None = None,
    track: str | None = None,
) -> dict[int, dict]:
    with SessionLocal() as session:
        query = (
            session.query(
                Starter.horse_id,
                Starter.horse_name,
                func.count(Starter.won).label("starts"),
                func.sum(Starter.won).label("wins"),
                func.avg(Starter.odds).label("avg_odds"),
                func.avg(Starter.finish_position).label("avg_position"),
            )
            .filter(Starter.scratched == False, Starter.horse_id.isnot(None))
        )
        if horse_ids is not None:
            query = query.filter(Starter.horse_id.in_(horse_ids))
        if track:
            query = query.filter(func.lower(Starter.track) == track.lower())
        rows = query.group_by(Starter.horse_id).all()

    result: dict[int, dict] = {}
    for row in rows:
        starts = row.starts or 0
        wins = int(row.wins or 0)
        result[row.horse_id] = {
            "name": row.horse_name,
            "starts": starts,
            "wins": wins,
            "win_pct": round(wins / starts * 100, 1) if starts else 0.0,
            "avg_odds": round(float(row.avg_odds), 1) if row.avg_odds else None,
            "avg_position": round(float(row.avg_position), 1) if row.avg_position else None,
        }
    return dict(sorted(result.items(), key=lambda x: x[1]["starts"], reverse=True))


def load_driver_stats(driver_ids: list[int] | None = None) -> dict[int, dict]:
    with SessionLocal() as session:
        query = (
            session.query(
                Starter.driver_id,
                Starter.driver_name,
                func.count(Starter.won).label("starts"),
                func.sum(Starter.won).label("wins"),
            )
            .filter(Starter.scratched == False, Starter.driver_id.isnot(None))
        )
        if driver_ids is not None:
            query = query.filter(Starter.driver_id.in_(driver_ids))
        rows = query.group_by(Starter.driver_id).all()

    result: dict[int, dict] = {}
    for row in rows:
        starts = row.starts or 0
        wins = int(row.wins or 0)
        result[row.driver_id] = {
            "driver_name": row.driver_name,
            "starts": starts,
            "wins": wins,
            "win_pct": round(wins / starts * 100, 1) if starts else 0.0,
        }
    return dict(sorted(result.items(), key=lambda x: x[1]["starts"], reverse=True))


def load_recent_starts(horse_id: int, limit: int = 10) -> list[dict]:
    with SessionLocal() as session:
        rows = (
            session.query(Starter)
            .filter(Starter.horse_id == horse_id)
            .order_by(Starter.date.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return []
        columns = [c.name for c in Starter.__table__.columns if c.name != "id"]
        return [{col: getattr(row, col) for col in columns} for row in rows]