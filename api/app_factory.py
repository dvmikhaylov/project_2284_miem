from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .config import CORS_ORIGINS
from .database import Base, SessionLocal, engine
from .db_migrate import apply_sqlite_migrations
from .routers import catalog_router, dashboard_router, documents_router
from .services.catalog_sync import sync_process_catalog


def _init_db() -> None:
    Base.metadata.create_all(bind=engine)
    apply_sqlite_migrations(engine)
    db = SessionLocal()
    try:
        sync_process_catalog(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Document Intelligence API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return RedirectResponse(url="/docs")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(catalog_router)
    app.include_router(documents_router)
    app.include_router(dashboard_router)
    return app
