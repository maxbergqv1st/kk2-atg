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
