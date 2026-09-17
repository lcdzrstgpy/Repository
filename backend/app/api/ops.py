"""移库单 / 盘点单接口（契约 16.3 / 17.3）。

两组单据都遵循「单据与库存分离」：
- 移库单只有「执行移库」才动库存（出库仓 -N / 入库仓 +N）
- 盘点单只有「完成盘点」才按差异动库存
两者都只调用 `app/services/inventory_service.py::change_inventory()`，
不新增任何库存变更路径。
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, NotFoundException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Product, ProductSku, Warehouse
from app.models.inventory import Inventory
from app.models.ops import (
    STOCK_TAKE_STATUS_CANCELLED,
    STOCK_TAKE_STATUS_DOING,
    STOCK_TAKE_STATUS_DONE,
    TRANSFER_STATUS_CANCELLED,
    TRANSFER_STATUS_DRAFT,
    TRANSFER_STATUS_DONE,
    StockTake,
    StockTakeItem,
    StockTransfer,
    StockTransferItem,
    stock_take_status_text,
    transfer_status_text,
)
from app.models.user import SysUser
from app.schemas.ops import (
    StockTakeCreateIn,
    StockTakeItemsIn,
    TransferCreateIn,
    stock_take_brief,
    stock_take_detail,
    stock_take_item_out,
    transfer_brief,
    transfer_detail,
    transfer_item_out,
)
from app.services.inventory_service import (
    ORDER_TYPE_STOCK_TAKE,
    ORDER_TYPE_TRANSFER_IN,
    ORDER_TYPE_TRANSFER_OUT,
    change_inventory,
    lock_inventory_keys,
)

router = APIRouter(prefix="/api/stock-transfers", tags=["仓储侧·移库单"])
stock_take_router = APIRouter(prefix="/api/stock-takes", tags=["仓储侧·盘点单"])

# 数量统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


# ---------------------------------------------------------------- 通用工具
def _load_sku_maps(
    db: Session, sku_ids: set[int]
) -> tuple[dict[int, ProductSku], dict[int, Product]]:
    """批量取 SKU 与所属商品，避免逐行查询。"""
    skus = (
        {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
        if sku_ids
        else {}
    )
    product_ids = {s.product_id for s in skus.values()}
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids
        else {}
    )
    return skus, products


def _load_user_names(db: Session, user_ids: set[int]) -> dict[int, str]:
    """批量取操作人姓名，避免逐行查询。"""
    if not user_ids:
        return {}
    return {
        u.id: (u.real_name or u.username)
        for u in db.scalars(select(SysUser).where(SysUser.id.in_(user_ids)))
    }


def _load_warehouse_names(db: Session, warehouse_ids: set[int]) -> dict[int, str]:
    """批量取仓库名，避免逐行查询。"""
    if not warehouse_ids:
        return {}
    return {
        w.id: w.name for w in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))
    }


def _get_warehouse_or_fail(db: Session, warehouse_id: int) -> Warehouse:
    """校验仓库存在且启用（契约 16.3 校验 2）。"""
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise BizException("仓库不存在")
    if warehouse.status != 1:
        raise BizException("仓库已停用")
    return warehouse


# ---------------------------------------------------------------- 单号生成
def generate_transfer_no(db: Session, offset: int = 0) -> str:
    """生成单号：TR + yyyyMMdd + 4 位当日流水，如 TR202609160001。"""
    prefix = "TR" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(StockTransfer.no)).where(StockTransfer.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq + offset:04d}"


def generate_stock_take_no(db: Session, offset: int = 0) -> str:
    """生成单号：ST + yyyyMMdd + 4 位当日流水，如 ST202609160001。"""
    prefix = "ST" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(StockTake.no)).where(StockTake.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq + offset:04d}"


# ---------------------------------------------------------------- 移库单序列化
def build_transfer_briefs(db: Session, rows: list[StockTransfer]) -> list[dict]:
    """移库单列表元素批量序列化。"""
    if not rows:
        return []
    warehouse_ids = set()
    for row in rows:
        warehouse_ids.add(row.from_warehouse_id)
        warehouse_ids.add(row.to_warehouse_id)
    warehouses = _load_warehouse_names(db, warehouse_ids)
    users = _load_user_names(db, {row.created_by for row in rows if row.created_by})
    return [
        transfer_brief(
            row,
            from_warehouse_name=warehouses.get(row.from_warehouse_id),
            to_warehouse_name=warehouses.get(row.to_warehouse_id),
            created_by_name=users.get(row.created_by),
        )
        for row in rows
    ]


def build_transfer_detail(db: Session, transfer: StockTransfer) -> dict:
    """移库单详情序列化，含明细（带 sku_code / product_name / spec）。"""
    warehouses = _load_warehouse_names(
        db, {transfer.from_warehouse_id, transfer.to_warehouse_id}
    )
    users = _load_user_names(db, {transfer.created_by} if transfer.created_by else set())
    items = list(
        db.scalars(
            select(StockTransferItem)
            .where(StockTransferItem.transfer_id == transfer.id)
            .order_by(StockTransferItem.id.asc())
        )
    )
    skus, products = _load_sku_maps(db, {item.sku_id for item in items})
    item_dicts = [
        transfer_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    return transfer_detail(
        transfer,
        from_warehouse_name=warehouses.get(transfer.from_warehouse_id),
        to_warehouse_name=warehouses.get(transfer.to_warehouse_id),
        created_by_name=users.get(transfer.created_by),
        items=item_dicts,
    )


# ---------------------------------------------------------------- 盘点单序列化
def build_stock_take_briefs(db: Session, rows: list[StockTake]) -> list[dict]:
    """盘点单列表元素批量序列化。"""
    if not rows:
        return []
    warehouses = _load_warehouse_names(db, {row.warehouse_id for row in rows})
    users = _load_user_names(db, {row.created_by for row in rows if row.created_by})
    return [
        stock_take_brief(
            row,
            warehouse_name=warehouses.get(row.warehouse_id),
            created_by_name=users.get(row.created_by),
        )
        for row in rows
    ]


def build_stock_take_detail(db: Session, take: StockTake) -> dict:
    """盘点单详情序列化，含明细。"""
    warehouses = _load_warehouse_names(db, {take.warehouse_id})
    users = _load_user_names(db, {take.created_by} if take.created_by else set())
    items = list(
        db.scalars(
            select(StockTakeItem)
            .where(StockTakeItem.stock_take_id == take.id)
            .order_by(StockTakeItem.id.asc())
        )
    )
    skus, products = _load_sku_maps(db, {item.sku_id for item in items})
    item_dicts = [
        stock_take_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    return stock_take_detail(
        take,
        warehouse_name=warehouses.get(take.warehouse_id),
        created_by_name=users.get(take.created_by),
        items=item_dicts,
    )


# ---------------------------------------------------------------- 移库单接口
@router.post("", summary="创建移库单")
def create_stock_transfer(
    payload: TransferCreateIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """创建移库单（草稿）。建单不动库存，只有「执行移库」才动。"""
    # 校验 1：不能移库到同一个仓库
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise BizException("不能移库到同一个仓库")

    # 校验 2：两个仓库都存在且启用
    _get_warehouse_or_fail(db, payload.from_warehouse_id)
    _get_warehouse_or_fail(db, payload.to_warehouse_id)

    # 校验 4：SKU 存在且启用
    sku_ids = [item.sku_id for item in payload.items]
    sku_map = {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
    for sku_id in sku_ids:
        sku = sku_map.get(sku_id)
        if sku is None:
            raise BizException(f"SKU(id={sku_id})不存在")
        if sku.status != 1:
            raise BizException(f"SKU「{sku.sku_code}」已停用，无法移库")

    # 后端汇总数量，不信任前端传值
    total_count = sum((item.count for item in payload.items), Decimal("0"))

    # stock_transfer.no 有唯一索引：并发下可能撞号，用 savepoint 包住后重试
    transfer: StockTransfer | None = None
    for attempt in range(5):
        candidate = StockTransfer(
            no=generate_transfer_no(db, offset=attempt),
            from_warehouse_id=payload.from_warehouse_id,
            to_warehouse_id=payload.to_warehouse_id,
            status=TRANSFER_STATUS_DRAFT,
            total_count=total_count,
            remark=payload.remark,
            created_by=current_user.id,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
            transfer = candidate
            break
        except IntegrityError:
            continue
    if transfer is None:
        raise BizException("移库单号生成冲突，请稍后重试")

    for item in payload.items:
        db.add(
            StockTransferItem(
                transfer_id=transfer.id,
                sku_id=item.sku_id,
                count=item.count,
            )
        )
    db.commit()
    db.refresh(transfer)
    return ok(build_transfer_detail(db, transfer), msg="移库单创建成功")


@router.get("", summary="移库单列表")
def list_stock_transfers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: int | None = Query(None, description="移库单状态"),
    keyword: str | None = Query(None, description="单号 / 备注"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """移库单列表，支持 ?page=&page_size=&keyword=&status=。"""
    page, page_size = normalize_page(page, page_size)

    stmt = select(StockTransfer)
    count_stmt = select(func.count()).select_from(StockTransfer)
    if status is not None:
        stmt = stmt.where(StockTransfer.status == status)
        count_stmt = count_stmt.where(StockTransfer.status == status)
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        condition = or_(StockTransfer.no.like(pattern), StockTransfer.remark.like(pattern))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(StockTransfer.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_transfer_briefs(db, list(rows)), total, page, page_size))


@router.get("/{transfer_id}", summary="移库单详情")
def get_stock_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """移库单详情，含明细。"""
    transfer = db.get(StockTransfer, transfer_id)
    if transfer is None:
        raise NotFoundException("移库单不存在")
    return ok(build_transfer_detail(db, transfer))


@router.post("/{transfer_id}/finish", summary="执行移库")
def finish_stock_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """执行移库：草稿 → 已完成，出库仓 -N / 入库仓 +N。

    两次 `change_inventory` 调用（TRANSFER_OUT / TRANSFER_IN）在**同一事务**里提交：
    出库仓库存不足会抛 code=1001，整体回滚，入库仓不会凭空增加。

    并发保护分两层：
    1. 先锁移库单行，避免并发重复执行同一张单；
    2. **先按全局有序顺序预锁定出库仓 + 入库仓的全部库存行**（`lock_inventory_keys`），
       再调两次 `change_inventory`。否则两张方向相反的移库单（A→B 与 B→A）并发执行时，
       两次调用各自的加锁顺序可能相反，形成 ABBA 死锁（InnoDB 1213）。
    """
    transfer = db.scalars(
        select(StockTransfer).where(StockTransfer.id == transfer_id).with_for_update()
    ).first()
    if transfer is None:
        raise NotFoundException("移库单不存在")
    if transfer.status != TRANSFER_STATUS_DRAFT:
        raise BizException(
            f"移库单当前状态为「{transfer_status_text(transfer.status)}」，无法执行移库操作"
        )

    items = list(
        db.scalars(select(StockTransferItem).where(StockTransferItem.transfer_id == transfer.id))
    )
    if not items:
        raise BizException("移库单没有明细，无法执行移库")

    # 预锁定：把出库仓与入库仓涉及的全部 (sku_id, warehouse_id) 合并后按同一顺序锁住，
    # 消除两次 change_inventory 之间加锁顺序不一致带来的 ABBA 死锁风险。
    lock_inventory_keys(
        db,
        [
            {
                "sku_id": item.sku_id,
                "warehouse_id": transfer.from_warehouse_id,
                "quantity": -Decimal(item.count or 0),
            }
            for item in items
        ]
        + [
            {
                "sku_id": item.sku_id,
                "warehouse_id": transfer.to_warehouse_id,
                "quantity": Decimal(item.count or 0),
            }
            for item in items
        ],
    )

    # 出库仓扣减（负数，库存不足会抛 code=1001 并整体回滚）
    change_inventory(
        db,
        [
            {
                "sku_id": item.sku_id,
                "warehouse_id": transfer.from_warehouse_id,
                "quantity": -Decimal(item.count or 0),
            }
            for item in items
        ],
        transfer.no,
        ORDER_TYPE_TRANSFER_OUT,
        current_user.id,
    )
    # 入库仓增加（正数），与上一笔同一事务
    change_inventory(
        db,
        [
            {
                "sku_id": item.sku_id,
                "warehouse_id": transfer.to_warehouse_id,
                "quantity": Decimal(item.count or 0),
            }
            for item in items
        ],
        transfer.no,
        ORDER_TYPE_TRANSFER_IN,
        current_user.id,
    )

    transfer.status = TRANSFER_STATUS_DONE
    transfer.finished_at = datetime.now()
    db.commit()
    db.refresh(transfer)
    return ok(build_transfer_detail(db, transfer), msg="移库完成")


@router.post("/{transfer_id}/cancel", summary="作废移库单")
def cancel_stock_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """作废移库单：仅草稿可作废，不动库存（草稿从未动过库存）。"""
    transfer = db.scalars(
        select(StockTransfer).where(StockTransfer.id == transfer_id).with_for_update()
    ).first()
    if transfer is None:
        raise NotFoundException("移库单不存在")
    if transfer.status != TRANSFER_STATUS_DRAFT:
        raise BizException(
            f"移库单当前状态为「{transfer_status_text(transfer.status)}」，无法执行作废操作"
        )

    transfer.status = TRANSFER_STATUS_CANCELLED
    db.commit()
    db.refresh(transfer)
    return ok(build_transfer_detail(db, transfer), msg="移库单已作废")


# ---------------------------------------------------------------- 盘点单接口
@stock_take_router.post("", summary="新建盘点单")
def create_stock_take(
    payload: StockTakeCreateIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """新建盘点单：自动快照账面数量（inventory.quantity），建单不动库存。"""
    _get_warehouse_or_fail(db, payload.warehouse_id)

    # sku_ids 为空 → 取该仓库所有已有库存记录的 SKU（契约 17.3）
    sku_ids = list(dict.fromkeys(payload.sku_ids or []))
    if not sku_ids:
        sku_ids = list(
            db.scalars(
                select(Inventory.sku_id).where(Inventory.warehouse_id == payload.warehouse_id)
            )
        )
        if not sku_ids:
            raise BizException("该仓库没有库存记录，无法建盘点单")
    else:
        # 指定了 SKU：必须都存在且启用
        sku_map = {
            s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))
        }
        for sku_id in sku_ids:
            sku = sku_map.get(sku_id)
            if sku is None:
                raise BizException(f"SKU(id={sku_id})不存在")
            if sku.status != 1:
                raise BizException(f"SKU「{sku.sku_code}」已停用，无法盘点")

    # 一次性批量取账面数量，避免逐行查询；无库存行则记 0
    book_map = {
        row.sku_id: Decimal(row.quantity or 0)
        for row in db.scalars(
            select(Inventory).where(
                Inventory.warehouse_id == payload.warehouse_id,
                Inventory.sku_id.in_(sku_ids),
            )
        )
    }
    total_count = sum((book_map.get(sku_id, Decimal("0")) for sku_id in sku_ids), Decimal("0"))

    # stock_take.no 有唯一索引：并发下可能撞号，用 savepoint 包住后重试
    take: StockTake | None = None
    for attempt in range(5):
        candidate = StockTake(
            no=generate_stock_take_no(db, offset=attempt),
            warehouse_id=payload.warehouse_id,
            status=STOCK_TAKE_STATUS_DOING,
            total_count=total_count,
            diff_count=Decimal("0.00"),
            remark=payload.remark,
            created_by=current_user.id,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
            take = candidate
            break
        except IntegrityError:
            continue
    if take is None:
        raise BizException("盘点单号生成冲突，请稍后重试")

    for sku_id in sku_ids:
        book = (book_map.get(sku_id, Decimal("0"))).quantize(CENT, rounding=ROUND_HALF_UP)
        db.add(
            StockTakeItem(
                stock_take_id=take.id,
                sku_id=sku_id,
                book_quantity=book,
                # 建单时实盘数量默认等于账面数量，差异为 0
                actual_quantity=book,
                diff_quantity=Decimal("0.00"),
            )
        )
    db.commit()
    db.refresh(take)
    return ok(build_stock_take_detail(db, take), msg="盘点单创建成功")


@stock_take_router.get("", summary="盘点单列表")
def list_stock_takes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: int | None = Query(None, description="盘点单状态"),
    warehouse_id: int | None = Query(None, description="按仓库筛选"),
    keyword: str | None = Query(None, description="单号 / 备注"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """盘点单列表，支持 ?page=&page_size=&keyword=&status=&warehouse_id=。"""
    page, page_size = normalize_page(page, page_size)

    stmt = select(StockTake)
    count_stmt = select(func.count()).select_from(StockTake)
    conditions = []
    if status is not None:
        conditions.append(StockTake.status == status)
    if warehouse_id is not None:
        conditions.append(StockTake.warehouse_id == warehouse_id)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        condition = or_(StockTake.no.like(pattern), StockTake.remark.like(pattern))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(StockTake.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_stock_take_briefs(db, list(rows)), total, page, page_size))


@stock_take_router.get("/{take_id}", summary="盘点单详情")
def get_stock_take(
    take_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """盘点单详情，含明细。"""
    take = db.get(StockTake, take_id)
    if take is None:
        raise NotFoundException("盘点单不存在")
    return ok(build_stock_take_detail(db, take))


@stock_take_router.put("/{take_id}/items", summary="录入实盘数量")
def update_stock_take_items(
    take_id: int,
    payload: StockTakeItemsIn,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """录入实盘数量。仅「盘点中」可录入，允许部分录入（未传的行保持原值）。

    并发保护：先锁盘点单行，避免与「完成盘点 / 作废」并发冲突。
    """
    take = db.scalars(
        select(StockTake).where(StockTake.id == take_id).with_for_update()
    ).first()
    if take is None:
        raise NotFoundException("盘点单不存在")
    if take.status != STOCK_TAKE_STATUS_DOING:
        raise BizException(
            f"盘点单当前状态为「{stock_take_status_text(take.status)}」，无法录入实盘数量"
        )

    items = {
        item.id: item
        for item in db.scalars(select(StockTakeItem).where(StockTakeItem.stock_take_id == take.id))
    }
    for line in payload.items:
        item = items.get(line.item_id)
        if item is None:
            raise BizException("盘点明细不存在")
        item.actual_quantity = Decimal(line.actual_quantity).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        # 未传行备注时保持原值，避免部分录入把已有备注清空
        if line.remark is not None:
            item.remark = line.remark

    db.commit()
    db.refresh(take)
    return ok(build_stock_take_detail(db, take), msg="实盘数量已保存")


@stock_take_router.post("/{take_id}/finish", summary="完成盘点")
def finish_stock_take(
    take_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """完成盘点：按「差异 = 实盘 - 账面」调整库存。

    只对 `diff != 0` 的行调一次 `change_inventory`（多行合并成一次调用），
    差异为负时由库存服务校验可用量；写回明细 diff_quantity、主表 diff_count /
    status / finished_at，全部在同一事务提交。

    并发保护：先锁盘点单行，避免并发重复完成、重复调库存。
    """
    take = db.scalars(
        select(StockTake).where(StockTake.id == take_id).with_for_update()
    ).first()
    if take is None:
        raise NotFoundException("盘点单不存在")
    if take.status != STOCK_TAKE_STATUS_DOING:
        raise BizException(
            f"盘点单当前状态为「{stock_take_status_text(take.status)}」，无法完成盘点操作"
        )

    items = list(
        db.scalars(
            select(StockTakeItem)
            .where(StockTakeItem.stock_take_id == take.id)
            .order_by(StockTakeItem.id.asc())
        )
    )

    # 逐行算差异；只有 diff != 0 的行才需要动库存
    changes: list[dict] = []
    diff_total = Decimal("0.00")
    diffs: dict[int, Decimal] = {}
    for item in items:
        diff = (Decimal(item.actual_quantity or 0) - Decimal(item.book_quantity or 0)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        diffs[item.id] = diff
        diff_total += diff
        if diff != 0:
            changes.append(
                {"sku_id": item.sku_id, "warehouse_id": take.warehouse_id, "quantity": diff}
            )

    # 全部差异为 0 时也允许完成，此时不写流水
    if changes:
        change_inventory(
            db,
            changes,
            take.no,
            ORDER_TYPE_STOCK_TAKE,
            current_user.id,
            remark=f"盘点单 {take.no}",
        )

    # 写回每行差异与主表汇总
    for item in items:
        item.diff_quantity = diffs[item.id]
    take.diff_count = diff_total
    take.status = STOCK_TAKE_STATUS_DONE
    take.finished_at = datetime.now()
    db.commit()
    db.refresh(take)
    return ok(build_stock_take_detail(db, take), msg="盘点完成")


@stock_take_router.post("/{take_id}/cancel", summary="作废盘点单")
def cancel_stock_take(
    take_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """作废盘点单：仅「盘点中」可作废，不动库存。"""
    take = db.scalars(
        select(StockTake).where(StockTake.id == take_id).with_for_update()
    ).first()
    if take is None:
        raise NotFoundException("盘点单不存在")
    if take.status != STOCK_TAKE_STATUS_DOING:
        raise BizException(
            f"盘点单当前状态为「{stock_take_status_text(take.status)}」，无法执行作废操作"
        )

    take.status = STOCK_TAKE_STATUS_CANCELLED
    db.commit()
    db.refresh(take)
    return ok(build_stock_take_detail(db, take), msg="盘点单已作废")


def register_ops_routers(app) -> None:
    """把移库单与盘点单两组路由挂到应用上。"""
    for item in (router, stock_take_router):
        app.include_router(item)
