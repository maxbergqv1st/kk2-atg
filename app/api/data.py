from fastapi import APIRouter, HTTPException

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
    try:
        return get_stats()
    except NoDatabaseDataError:
        raise HTTPException(status_code=404, detail="Ingen data i databasen")


@router.get("/preview")
def data_preview(n: int = 10) -> list[dict]:
    try:
        return get_preview(n)
    except NoDatabaseDataError:
        raise HTTPException(status_code=404, detail="Ingen data i databasen")
