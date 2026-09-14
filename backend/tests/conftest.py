from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters import get_sentry_adapter
from app.config import Settings, get_settings
from app.db import Base, build_engine, get_db
from app.main import create_app
from app.models import Category, Sku, User
from app.security import hash_password


class FakeSentryAdapter:
    def __init__(self):
        self.items = []
        self.orders = []
        self.cancelled = []

    async def push_item(self, sku):
        self.items.append(sku.id)
        return {"canonical_id": str(sku.external_id)}

    async def create_sales_order(self, submission, order):
        self.orders.append(order.id)
        return {"canonical_id": str(uuid4())}

    async def cancel_sales_order(self, order, reason):
        self.cancelled.append((order.id, reason))
        return {"canonical_id": str(order.external_id)}


@pytest_asyncio.fixture
async def api(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = build_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(username="ops", password_hash=hash_password("password123"), role="ops")
        root = Category(category_name="家居用品")
        session.add_all([user, root])
        await session.flush()
        leaf = Category(category_name="杯具", parent_id=root.id, code_prefix="A001")
        session.add(leaf)
        await session.flush()
        sku = Sku(
            external_id=uuid4(),
            sku_code="A001-1",
            category_id=leaf.id,
            item_name="玻璃杯",
            code_status="active",
            promoted_at=datetime.now(timezone.utc),
        )
        leaf.seq_counter = 1
        session.add(sku)
        await session.commit()
        seed = {"leaf_id": leaf.id, "sku_id": sku.id, "sku_external_id": str(sku.external_id)}

    settings = Settings(
        database_url=database_url,
        jwt_secret="test-jwt-secret-with-at-least-32-bytes",
        wms_api_token="test-wms-token-123456",
        webhook_secret="test-webhook-secret-123456",
        seed_default_categories=False,
    )
    fake_adapter = FakeSentryAdapter()
    app = create_app(with_lifespan=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_sentry_adapter] = lambda: fake_adapter

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "ops", "password": "password123"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        yield {
            "client": client,
            "ops_headers": {"Authorization": f"Bearer {token}"},
            "wms_headers": {"X-WMS-Token": settings.wms_api_token},
            "settings": settings,
            "session_factory": session_factory,
            "adapter": fake_adapter,
            **seed,
        }
    await engine.dispose()
