from fastapi import APIRouter, HTTPException

from app.models.models import AiRequest, AiResponse
from app.services.ai_service import ask_question
from app import db

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=AiResponse)
def ask(req: AiRequest) -> AiResponse:
    if db.count_starters() == 0:
        raise HTTPException(
            status_code=400,
            detail="Inget dataset har laddats upp. Hamta data via /data/fetch forst.",
        )
    try:
        result = ask_question(req.question)
        return AiResponse(**result.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Modellfel: {e}")
