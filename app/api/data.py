import io

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from app.models.models import FetchRequest, UploadResponse
from app.services.data_service import (
    AtgFetchError,
    NoDatabaseDataError,
    fetch_and_store,
    get_count,
    get_dates,
    get_preview,
    get_starters,
    get_stats,
)

router = APIRouter(prefix="/data", tags=["data"])

_uploaded_df: pd.DataFrame | None = None


@router.post("/upload", response_model=UploadResponse)
async def upload_csv(file: UploadFile) -> UploadResponse:
    global _uploaded_df

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Filen maste vara en CSV-fil (.csv)")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Filen ar tom")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Kunde inte lasa CSV-filen")

    _uploaded_df = df
    return UploadResponse.from_dataframe(df)


@router.get("/count")
def data_count() -> dict:
    return {"rows": get_count()}


@router.get("/dates")
def data_dates() -> list[str]:
    return get_dates()


@router.get("/starters")
def data_starters(limit: int = 50) -> list[dict]:
    return get_starters(limit)


@router.post("/fetch", response_model=UploadResponse)
def fetch_data(req: FetchRequest) -> UploadResponse:
    try:
        df = fetch_and_store(req.days, req.dataset)
    except AtgFetchError as e:
        raise HTTPException(
            status_code=502,
            detail=f"ATG-hämtning misslyckades för {e.day}: {e.cause}",
        )
    except NoDatabaseDataError:
        raise HTTPException(status_code=404, detail="Ingen data i databasen")

    return UploadResponse.from_dataframe(df)


@router.get("/stats")
def data_stats() -> dict:
    if _uploaded_df is not None:
        return _uploaded_df.describe().to_dict()
    try:
        return get_stats()
    except NoDatabaseDataError:
        raise HTTPException(status_code=404, detail="Inget dataset har laddats upp")


@router.get("/preview")
def data_preview(n: int = 10) -> list[dict]:
    try:
        return get_preview(n)
    except NoDatabaseDataError:
        raise HTTPException(status_code=404, detail="Ingen data i databasen")
