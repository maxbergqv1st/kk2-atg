import logging

from fastapi import APIRouter, HTTPException

from app.models.models import AiRequest, AiResponse
from app.services.ai_service import ask_question
from app import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=AiResponse)
def ask(req: AiRequest) -> AiResponse:
    if db.count_starters() == 0:
        raise HTTPException(
            status_code=400,
            detail="Inget dataset har laddats upp. Hamta data via /data/fetch forst.",
        )
    logger.info("AI-fraga: %s", req.question)
    try:
        result = ask_question(req.question)
        return AiResponse(**result.model_dump())
    except Exception as e:
        logger.error("Modellfel for fraga '%s': %s", req.question, e)
        raise HTTPException(status_code=500, detail=f"Modellfel: {e}")
