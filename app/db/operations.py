import numpy as np
import pandas as pd
from sqlalchemy import func

from app.db.schema import SessionLocal, Starter


"""_clean: sql tar inte np värden. Konverterar till vanliga python typer"""

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

"""tar dfen med _clean funktionen och skickar till db  """

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
    df["date"] = pd.to_datetime(df["date"])
    return df


def _query_entity_stats(id_col, name_col, name_filter: str | None = None) -> pd.DataFrame:
    with SessionLocal() as session:
        query = (
            session.query(
                id_col.label("entity_id"),
                name_col.label("name"),
                func.count(Starter.won).label("starts"),
                func.sum(Starter.won).label("wins"),
                func.avg(Starter.odds).label("avg_odds"),
                func.avg(Starter.finish_position).label("avg_position"),
            )
            .filter(Starter.scratched == False, id_col.isnot(None))
        )
        if name_filter:
            query = query.filter(func.lower(name_col) == name_filter.lower())
        rows = query.group_by(id_col).all()

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["entity_id", "name", "starts", "wins", "avg_odds", "avg_position"])
    df["win_pct"] = (df["wins"] / df["starts"] * 100).round(1)
    return df.sort_values("starts", ascending=False)


def load_horse_stats(horse_name: str | None = None) -> pd.DataFrame:
    return _query_entity_stats(Starter.horse_id, Starter.horse_name, horse_name)


def load_driver_stats(driver_name: str | None = None) -> pd.DataFrame:
    return _query_entity_stats(Starter.driver_id, Starter.driver_name, driver_name)


def load_recent_starts(horse_name: str, limit: int = 10) -> list[dict]:
    with SessionLocal() as session:
        rows = (
            session.query(Starter)
            .filter(func.lower(Starter.horse_name) == horse_name.lower())
            .order_by(Starter.date.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return []
        columns = [c.name for c in Starter.__table__.columns if c.name != "id"]
        return [{col: getattr(row, col) for col in columns} for row in rows]