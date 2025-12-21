from fastapi import FastAPI
from .core.logging import setup_logging
from .core.config import ensure_dirs
from .routers import health,request as analyze, resolve


def create_app() -> FastAPI:
    setup_logging()
    ensure_dirs()

    app = FastAPI(
        title="Creator Growth Lab API",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(analyze.router)
    app.include_router(resolve.router)

    return app

app = create_app()
