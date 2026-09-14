from collections.abc import AsyncIterator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    metadata = MetaData(schema="hub")


def build_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite+"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite+"):
        engine = engine.execution_options(schema_translate_map={"hub": None})
    return engine


engine = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def create_schema_and_tables(target_engine: AsyncEngine = engine) -> None:
    async with target_engine.begin() as conn:
        if target_engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS hub"))
        await conn.run_sync(Base.metadata.create_all)
