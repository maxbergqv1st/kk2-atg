from fastapi import FastAPI

from app.api.data import router as data_router
from app.api.health import router as health_router

app = FastAPI(title="KK2 ATG")

app.include_router(health_router)
app.include_router(data_router)