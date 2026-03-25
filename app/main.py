from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import ensure_database_parent_dir, get_settings
from app.db.connection import init_db
from app.routers import admin_api, catch_up, exa_webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_path = Path(settings.database_path)
    ensure_database_parent_dir(db_path)
    init_db(db_path)
    yield


app = FastAPI(
    title="Exa → Ashby pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(exa_webhook.router)
app.include_router(admin_api.router)
app.include_router(catch_up.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
