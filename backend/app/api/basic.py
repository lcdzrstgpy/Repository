"""基础数据 CRUD（契约 5.2）：仓库、商品、SKU、往来单位、用户。

五组接口结构完全一致，统一由 build_crud_router 生成：
    GET     {prefix}            列表（?page=&page_size=&keyword=）
    GET     {prefix}/options    下拉选项（部分实体）
    GET     {prefix}/{id}       详情
    POST    {prefix}            新增（仅 admin）
    PUT     {prefix}/{id}       修改（仅 admin）
    DELETE  {prefix}/{id}       删除（软删，置 status=0，仅 admin）
"""

from typing import Any, Callable

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, NotFoundException, normalize_page, ok, paginate
from app.core.security import hash_password, require_roles
from app.models.basic import Partner, Product, ProductSku, Warehouse
from app.models.inventory import Inventory
from app.models.user import SysUser
from app.schemas import basic as bs
from app.schemas.serializers import fmt_dec, partner_out, product_out, sku_out, user_out, warehouse_out

# ---------------------------------------------------------------- 通用 CRUD 工厂


def _commit(db: Session, err_msg: str) -> None:
    """提交事务，唯一键冲突等异常转成业务异常。"""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizException(err_msg)


def build_crud_router(
    *,
    prefix: str,
    tag: str,
    label: str,
    model: Any,
    create_schema: Any,
    update_schema: Any,
    serializer: Callable[[Any, Session], dict],
    keyword_columns: tuple = (),
    keyword_filter: Callable[[str], Any] | None = None,
    extra_filters: dict[str, Callable[[str], Any]] | None = None,
    unique_fields: dict[str, str] | None = None,
    write_roles: tuple[str, ...] = ("admin",),
    read_roles: tuple[str, ...] = ("*",),
    prepare_create: Callable[[Session, dict], dict] | None = None,
    prepare_update: Callable[[Session, dict, Any], dict] | None = None,
    validate: Callable[[Session, dict], None] | None = None,
    options: Callable[[Session, dict], list[dict]] | None = None,
) -> APIRouter:
    """按统一的五组接口结构生成路由。

    :param extra_filters: 额外精确过滤钩子，形如 `{"type": 条件构造器}`。
        列表接口会按 key 从 query 参数里取值，值非空时把构造器返回的 SQL 条件加入 where，
        未配置该钩子的实体（warehouse / product / sku）行为不变。
    """
    router = APIRouter(prefix=prefix, tags=[tag])
    read_dep = require_roles(*read_roles)
    write_dep = require_roles(*write_roles)

    def get_or_404(db: Session, item_id: int) -> Any:
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFoundException(f"{label}不存在")
        return obj

    def check_unique(db: Session, data: dict, exclude_id: int | None = None) -> None:
        for field, field_label in (unique_fields or {}).items():
            value = data.get(field)
            if value is None:
                continue
            stmt = select(model).where(getattr(model, field) == value)
            if exclude_id is not None:
                stmt = stmt.where(model.id != exclude_id)
            if db.scalars(stmt).first() is not None:
                raise BizException(f"{field_label}「{value}」已存在")

    # -------------------------------------------------- 列表
    @router.get("", summary=f"{label}列表")
    def list_items(
        request: Request,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, description="每页条数"),
        keyword: str | None = Query(None, description="关键字"),
        db: Session = Depends(get_db),
        _current_user: SysUser = Depends(read_dep),
    ):
        page, page_size = normalize_page(page, page_size)
        conditions = []
        # 额外精确过滤：query 参数名 → 条件构造器，未传或空串时跳过
        for param_name, filter_factory in (extra_filters or {}).items():
            raw_value = (request.query_params.get(param_name) or "").strip()
            if raw_value:
                conditions.append(filter_factory(raw_value))
        kw = (keyword or "").strip()
        if kw:
            if keyword_filter is not None:
                conditions.append(keyword_filter(kw))
            elif keyword_columns:
                conditions.append(or_(*[col.like(f"%{kw}%") for col in keyword_columns]))

        total = db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
        rows = db.scalars(
            select(model)
            .where(*conditions)
            .order_by(model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return ok(paginate([serializer(row, db) for row in rows], total, page, page_size))

    # -------------------------------------------------- 下拉选项（必须先于 /{id} 注册）
    if options is not None:

        @router.get("/options", summary=f"{label}下拉选项")
        def list_options(
            request: Request,
            db: Session = Depends(get_db),
            _current_user: SysUser = Depends(read_dep),
        ):
            return ok(options(db, dict(request.query_params)))

    # -------------------------------------------------- 详情
    @router.get("/{item_id}", summary=f"{label}详情")
    def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        _current_user: SysUser = Depends(read_dep),
    ):
        return ok(serializer(get_or_404(db, item_id), db))

    # -------------------------------------------------- 新增
    @router.post("", summary=f"新增{label}")
    def create_item(
        payload: create_schema,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
        _current_user: SysUser = Depends(write_dep),
    ):
        data = payload.model_dump()
        if validate is not None:
            validate(db, data)
        check_unique(db, data)
        if prepare_create is not None:
            data = prepare_create(db, data)
        obj = model(**data)
        db.add(obj)
        _commit(db, f"{label}新增失败，请检查编码等唯一字段是否重复")
        db.refresh(obj)
        return ok(serializer(obj, db), msg="新增成功")

    # -------------------------------------------------- 修改
    @router.put("/{item_id}", summary=f"修改{label}")
    def update_item(
        item_id: int,
        payload: update_schema,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
        _current_user: SysUser = Depends(write_dep),
    ):
        obj = get_or_404(db, item_id)
        data = payload.model_dump(exclude_unset=True)
        if validate is not None:
            validate(db, data)
        check_unique(db, data, exclude_id=obj.id)
        if prepare_update is not None:
            data = prepare_update(db, data, obj)
        for field, value in data.items():
            setattr(obj, field, value)
        _commit(db, f"{label}修改失败，请检查编码等唯一字段是否重复")
        db.refresh(obj)
        return ok(serializer(obj, db), msg="修改成功")

    # -------------------------------------------------- 删除（软删）
    @router.delete("/{item_id}", summary=f"删除{label}")
    def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        _current_user: SysUser = Depends(write_dep),
    ):
        obj = get_or_404(db, item_id)
        obj.status = 0
        _commit(db, f"{label}删除失败")
        return ok(None, msg="删除成功")

    return router


# ---------------------------------------------------------------- 各实体的钩子


def _validate_sku(db: Session, data: dict) -> None:
    """SKU 关联的商品必须存在。"""
    product_id = data.get("product_id")
    if product_id is not None and db.get(Product, product_id) is None:
        raise BizException(f"关联商品(id={product_id})不存在")


def _prepare_user_create(db: Session, data: dict) -> dict:
    """用户新增：明文密码转 bcrypt 哈希，丢弃明文字段。"""
    password = data.pop("password", None)
    if not password:
        raise BizException("密码不能为空")
    data["password_hash"] = hash_password(password)
    return data


def _prepare_user_update(db: Session, data: dict, obj: SysUser) -> dict:
    """用户修改：传了 password 才更新哈希。"""
    password = data.pop("password", None)
    if password:
        data["password_hash"] = hash_password(password)
    return data


# ---------------------------------------------------------------- 路由注册

warehouse_router = build_crud_router(
    prefix="/api/warehouses",
    tag="基础数据·仓库",
    label="仓库",
    model=Warehouse,
    create_schema=bs.WarehouseCreate,
    update_schema=bs.WarehouseUpdate,
    serializer=lambda row, db: warehouse_out(row),
    keyword_columns=(Warehouse.code, Warehouse.name),
    unique_fields={"code": "仓库编码"},
    options=lambda db, params: [
        {"id": w.id, "name": w.name}
        for w in db.scalars(
            select(Warehouse).where(Warehouse.status == 1).order_by(Warehouse.id.asc())
        ).all()
    ],
)

product_router = build_crud_router(
    prefix="/api/products",
    tag="基础数据·商品",
    label="商品",
    model=Product,
    create_schema=bs.ProductCreate,
    update_schema=bs.ProductUpdate,
    serializer=lambda row, db: product_out(row),
    keyword_columns=(Product.code, Product.name),
    unique_fields={"code": "商品编码"},
)


def _sku_keyword_filter(kw: str):
    """SKU 关键字同时匹配 SKU 编码、规格、所属商品名称。"""
    pattern = f"%{kw}%"
    product_ids = select(Product.id).where(Product.name.like(pattern))
    return or_(
        ProductSku.sku_code.like(pattern),
        ProductSku.spec.like(pattern),
        ProductSku.product_id.in_(product_ids),
    )


def _sku_serializer(row: ProductSku, db: Session) -> dict:
    return sku_out(row, db.get(Product, row.product_id))


def _sku_options(db: Session, params: dict) -> list[dict]:
    """SKU 下拉选项，name 取所属 product.name。"""
    rows = db.execute(
        select(ProductSku, Product)
        .join(Product, Product.id == ProductSku.product_id)
        .where(ProductSku.status == 1)
        .order_by(ProductSku.id.asc())
    ).all()
    return [
        {
            "id": sku.id,
            "sku_code": sku.sku_code,
            "name": product.name,
            "spec": sku.spec,
            "price": float(sku.price or 0),
            "min_stock": float(sku.min_stock or 0),
        }
        for sku, product in rows
    ]


sku_router = build_crud_router(
    prefix="/api/skus",
    tag="基础数据·SKU",
    label="SKU",
    model=ProductSku,
    create_schema=bs.SkuCreate,
    update_schema=bs.SkuUpdate,
    serializer=_sku_serializer,
    keyword_filter=_sku_keyword_filter,
    unique_fields={"sku_code": "SKU 编码"},
    validate=_validate_sku,
    options=_sku_options,
)


# ---------------------------------------------------------------- 运营货号库存查询

item_router = APIRouter(prefix="/api/item-query", tags=["运营侧·货号查询"])


@item_router.get("", summary="货号及库存查询")
def item_query(
    keyword: str | None = Query(None, description="货号 / 商品名称 / 规格"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """按货号或商品资料查询，只读返回每个仓库的库存余额。"""
    stmt = select(ProductSku, Product).join(Product, Product.id == ProductSku.product_id)
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        stmt = stmt.where(
            or_(
                ProductSku.sku_code.like(pattern),
                ProductSku.spec.like(pattern),
                Product.name.like(pattern),
            )
        )

    rows = db.execute(
        stmt.where(ProductSku.status == 1).order_by(ProductSku.id.desc())
    ).all()
    sku_ids = [sku.id for sku, _product in rows]
    stock_map: dict[int, list[dict]] = {}
    if sku_ids:
        inventories = db.execute(
            select(Inventory, Warehouse)
            .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
            .where(Inventory.sku_id.in_(sku_ids))
            .order_by(Inventory.sku_id.asc(), Warehouse.id.asc())
        ).all()
        for inventory, warehouse in inventories:
            quantity = inventory.quantity or 0
            reserved = inventory.reserved_quantity or 0
            stock_map.setdefault(inventory.sku_id, []).append(
                {
                    "warehouse_id": warehouse.id,
                    "warehouse_name": warehouse.name,
                    "quantity": fmt_dec(quantity),
                    "reserved_quantity": fmt_dec(reserved),
                    "available_quantity": fmt_dec(quantity - reserved),
                }
            )

    return ok(
        [
            {
                "id": sku.id,
                "item_no": sku.sku_code,
                "sku_code": sku.sku_code,
                "product_name": product.name,
                "spec": sku.spec,
                "stocks": stock_map.get(sku.id, []),
            }
            for sku, product in rows
        ]
    )


def _partner_options(db: Session, params: dict) -> list[dict]:
    """往来单位下拉选项，type 可选（1 客户 / 2 供应商 / 3 两者）。"""
    stmt = select(Partner).where(Partner.status == 1)
    raw_type = (params.get("type") or "").strip()
    if raw_type:
        try:
            partner_type = int(raw_type)
        except ValueError:
            raise BizException("type 参数必须为整数：1 客户 / 2 供应商 / 3 两者都是")
        # type=3 的往来单位在任一类型筛选下都应可选
        stmt = stmt.where(or_(Partner.type == partner_type, Partner.type == 3))
    rows = db.scalars(stmt.order_by(Partner.id.asc())).all()
    return [{"id": p.id, "name": p.name} for p in rows]


def _partner_type_filter(raw_value: str):
    """往来单位类型精确过滤（1 客户 / 2 供应商 / 3 两者都是）。"""
    try:
        partner_type = int(raw_value)
    except ValueError:
        raise BizException("type 参数必须为整数：1 客户 / 2 供应商 / 3 两者都是")
    return Partner.type == partner_type


partner_router = build_crud_router(
    prefix="/api/partners",
    tag="基础数据·往来单位",
    label="往来单位",
    model=Partner,
    create_schema=bs.PartnerCreate,
    update_schema=bs.PartnerUpdate,
    serializer=lambda row, db: partner_out(row),
    keyword_columns=(Partner.name, Partner.contact, Partner.phone),
    options=_partner_options,
    extra_filters={"type": _partner_type_filter},
)


def _user_role_filter(raw_value: str):
    """用户角色精确过滤（契约 3.1）。"""
    return SysUser.role == raw_value


user_router = build_crud_router(
    prefix="/api/users",
    tag="基础数据·用户",
    label="用户",
    model=SysUser,
    create_schema=bs.UserCreate,
    update_schema=bs.UserUpdate,
    serializer=lambda row, db: user_out(row),
    keyword_columns=(SysUser.username, SysUser.real_name),
    unique_fields={"username": "登录名"},
    write_roles=("admin",),
    read_roles=("admin",),
    prepare_create=_prepare_user_create,
    prepare_update=_prepare_user_update,
    extra_filters={"role": _user_role_filter},
)


def register_basic_routers(app) -> None:
    """把五组基础数据路由挂到应用上。"""
    for router in (
        warehouse_router,
        product_router,
        sku_router,
        item_router,
        partner_router,
        user_router,
    ):
        app.include_router(router)
