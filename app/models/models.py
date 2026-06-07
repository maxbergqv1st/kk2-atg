from typing import Literal

import pandas as pd
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class UploadResponse(BaseModel):
    rows: int
    columns: list[str]
    dtypes: dict[str, str]

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "UploadResponse":
        return cls(
            rows=len(df),
            columns=df.columns.tolist(),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
        )

class FetchRequest(BaseModel):
    days: int = 3
    dataset: Literal["starters", "horses"] = "starters"


class AiRequest(BaseModel):
    question: str


class AiResponse(BaseModel):
    question: str
    intent: str
    answer: str
    model: str


class UpcomingRequest(BaseModel):
    game_type: Literal["V64", "V75", "V85", "V86"] = "V86"
    date: str = "2026-06-10"


class HorseOverallStats(BaseModel):
    starts: int
    wins: int
    win_pct: float
    avg_odds: float | None
    avg_position: float | None


class HorseTrackStats(BaseModel):
    track: str
    starts: int
    wins: int
    win_pct: float
    avg_position: float | None


class DriverOverallStats(BaseModel):
    driver_name: str
    starts: int
    wins: int
    win_pct: float


class HorseAnalysis(BaseModel):
    post_position: int | None
    horse_name: str | None
    horse_age: float | None
    driver_name: str | None
    overall: HorseOverallStats | None
    track: HorseTrackStats | None
    driver: DriverOverallStats | None


class RaceAnalysis(BaseModel):
    race_number: int | None
    track: str | None
    distance_m: float | None
    starters: list[HorseAnalysis]


class UpcomingGameResponse(BaseModel):
    game_type: str
    date: str
    races: list[RaceAnalysis]
    total_horses: int
    horses_with_history: int
