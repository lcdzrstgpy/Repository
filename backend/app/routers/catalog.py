from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import SentryAdapterError, SentryWMSAdapter, get_sentry_adapter
from app.db import get_db
from app.deps import current_ops_user, require_wms_token
from app.models import Category, Sku, User
from app.schemas import CategoryCreate, CategoryResponse, CategoryTreeResponse, SkuCreate, SkuResponse
from app.services import create_sku


router = APIRouter(prefix="/catalog", tags=["catalog"])
warehouse_router = APIRouter(
    prefix="/warehouse/catalog", tags=["warehouse-catalog"], dependencies=[Depends(require_wms_token)]
)


async def search_active_skus(session: AsyncSession, q: str, limit: int) -> list[Sku]:
    """按货号或商品名模糊检索可引用的正式货号（运营端与仓库端共用）。"""
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Sku)
        .where(
            Sku.code_status == "active",
            Sku.is_active.is_(True),
            or_(Sku.sku_code.ilike(pattern), Sku.item_name.ilike(pattern)),
        )
        .order_by(Sku.sku_code)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


@router.get("/categories", response_model=list[CategoryTreeResponse])
async def list_categories(
    _: User = Depends(current_ops_user), session: AsyncSession = Depends(get_db)
):
    categories = list(
        (
            await session.scalars(
                select(Category).where(Category.is_active.is_(True)).order_by(Category.parent_id, Category.id)
            )
        ).all()
    )
    children_by_parent: dict[int, list[CategoryTreeResponse]] = {}
    for category in categories:
        if category.parent_id is not None:
            children_by_parent.setdefault(category.parent_id, []).append(
                CategoryTreeResponse.model_validate(category)
            )
    return [
        CategoryTreeResponse(
            **CategoryResponse.model_validate(category).model_dump(),
            children=children_by_parent.get(category.id, []),
        )
        for category in categories
        if category.parent_id is None
    ]


@router.get("/skus/search", response_model=list[SkuResponse])
async def search_skus(
    q: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    return await search_active_skus(session, q, limit)


@warehouse_router.get("/categories", response_model=list[CategoryResponse])
async def warehouse_categories(session: AsyncSession = Depends(get_db)):
    return list((await session.scalars(select(Category).order_by(Category.parent_id, Category.id))).all())


@warehouse_router.get("/skus/search", response_model=list[SkuResponse])
async def warehouse_search_skus(
    q: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """仓库端改号 / 判重时的货号检索。

    与运营端 `GET /catalog/skus/search` 的差别只在认证方式（仓库端用
    `X-WMS-Token`），所以查询体共用 `search_active_skus`。只返回可引用的
    正式货号：`draft` 不允许被提交单引用。
    """
    return await search_active_skus(session, q, limit)


@warehouse_router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(body: CategoryCreate, session: AsyncSession = Depends(get_db)):
    if body.parent_id is None:
        if body.code_prefix is not None:
            raise HTTPException(status_code=422, detail="一级类目不能设置 code_prefix")
    else:
        parent = await session.get(Category, body.parent_id)
        if parent is None or parent.parent_id is not None:
            raise HTTPException(status_code=422, detail="类目树固定两层，parent_id 必须指向一级类目")
        if body.code_prefix is None:
            raise HTTPException(status_code=422, detail="二级类目必须设置 code_prefix")
    category = Category(**body.model_dump())
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


@warehouse_router.post("/skus", response_model=SkuResponse, status_code=201)
async def warehouse_create_sku(
    body: SkuCreate,
    session: AsyncSession = Depends(get_db),
    adapter: SentryWMSAdapter = Depends(get_sentry_adapter),
):
    sku = await create_sku(session, **body.model_dump())
    if sku.code_status == "active":
        try:
            await adapter.push_item(sku)
        except SentryAdapterError as exc:
            await session.rollback()
            raise HTTPException(status_code=502, detail=str(exc))
    await session.commit()
    await session.refresh(sku)
    return sku


@warehouse_router.get("/skus/drafts", response_model=list[SkuResponse])
async def list_draft_skus(session: AsyncSession = Depends(get_db)):
    return list(
        (
            await session.scalars(
                select(Sku).where(Sku.code_status == "draft").order_by(Sku.created_at)
            )
        ).all()
    )
