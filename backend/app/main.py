import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import SessionLocal, create_schema_and_tables
from app.routers import auth, catalog, submissions, system, warehouse, webhooks
from app.services import scan_timeouts, seed_reference_data


logger = logging.getLogger(__name__)


async def _timeout_scan_loop(interval_seconds: int) -> None:
    if interval_seconds <= 0:
        return
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with SessionLocal() as session:
                alerts = await scan_timeouts(session)
            if alerts:
                logger.warning("超时提醒扫描发出 %s 条提醒", len(alerts))
        except Exception:
            logger.exception("超时提醒扫描失败，将在下个周期重试")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await create_schema_and_tables()
    async with SessionLocal() as session:
        await seed_reference_data(
            session,
            seed_categories=settings.seed_default_categories,
            username=settings.bootstrap_username,
            password=settings.bootstrap_password,
        )
    task = asyncio.create_task(
        _timeout_scan_loop(settings.timeout_scan_interval_seconds)
    )
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan if with_lifespan else None,
    )
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(catalog.warehouse_router, prefix="/api/v1")
    app.include_router(submissions.router, prefix="/api/v1")
    app.include_router(warehouse.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
