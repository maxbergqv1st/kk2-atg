from fastapi import FastAPI

from app.schemas import HealthResponse

app = FastAPI(title="KK2 ATG")

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
  return HealthResponse(status=ok)