import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.ai import router as ai_router
from app.api.data import router as data_router
from app.api.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.chain import get_pipeline
    await asyncio.to_thread(get_pipeline)
    yield


app = FastAPI(title="KK2 ATG", lifespan=lifespan)

app.include_router(health_router)
app.include_router(data_router)
app.include_router(ai_router)

_static = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(_static / "index.html")
