import io
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.models.models import FetchRequest, UpcomingGameResponse, UpcomingRequest, UploadResponse
from app.services.data_service import (
    AtgFetchError,
    NoDatabaseDataError,
    UpcomingGameNotFoundError,
    analyze_upcoming,
    fetch_and_store,
    get_count,
    get_dates,
    get_preview,
    get_starters,
    get_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/upload", response_model=UploadResponse)
async def upload_csv(file: UploadFile, request: Request) -> UploadResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Filen maste vara en CSV-fil (.csv)")

    contents = await file.read()
    if not contents:
        logger.warning("Tom fil uppladdad: %s", file.filename)
        raise HTTPException(status_code=400, detail="Filen ar tom")

    max_size = 10 * 1024 * 1024  # 10 MB
    if len(contents) > max_size:
        logger.warning("For stor fil: %s (%d bytes)", file.filename, len(contents))
        raise HTTPException(status_code=400, detail="Filen ar for stor (max 10 MB)")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        logger.warning("Ogiltig CSV: %s", file.filename)
        raise HTTPException(status_code=400, detail="Kunde inte lasa CSV-filen")

    request.app.state.uploaded_df = df
    logger.info("CSV uppladdad: %s (%d rader)", file.filename, len(df))
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


@router.post("/upcoming", response_model=UpcomingGameResponse)
def upcoming_game(req: UpcomingRequest) -> UpcomingGameResponse:
    try:
        return analyze_upcoming(req.game_type, req.date)
    except UpcomingGameNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Inget {req.game_type}-spel hittades for {req.date}",
        )
    except AtgFetchError as e:
        raise HTTPException(
            status_code=502,
            detail=f"ATG-hamtning misslyckades: {e.cause}",
        )


@router.get("/stats")
def data_stats(request: Request) -> dict:
    uploaded_df = getattr(request.app.state, "uploaded_df", None)
    if uploaded_df is not None:
        return uploaded_df.describe().to_dict()
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
