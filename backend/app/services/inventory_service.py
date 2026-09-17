"""库存变更统一服务（契约 9.3 / 12.3）。

所有库存变动**必须**走 `change_inventory`，禁止在业务代码里直接 UPDATE 库存表。
库存预留（四阶段）走 `reserve_inventory` / `release_inventory`。
本模块只负责改数据，不负责提交事务——由调用方在同一个事务里 commit，
保证「扣库存 + 写出库单 + 改订单状态」要么全成功要么全回滚。
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.response import BizException
from app.models.basic import ProductSku, Warehouse
from app.models.inventory import Inventory, InventoryHistory

# 数量统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")

# 单据类型（契约 9.4 / 16.4 / 17.4）
ORDER_TYPE_SALES_OUT = "SALES_OUT"
ORDER_TYPE_PURCHASE_IN = "PURCHASE_IN"
ORDER_TYPE_ADJUST = "ADJUST"
ORDER_TYPE_TRANSFER_OUT = "TRANSFER_OUT"
ORDER_TYPE_TRANSFER_IN = "TRANSFER_IN"
ORDER_TYPE_STOCK_TAKE = "STOCK_TAKE"

# 单据类型中文名
ORDER_TYPE_TEXT: dict[str, str] = {
    ORDER_TYPE_SALES_OUT: "销售出库",
    ORDER_TYPE_PURCHASE_IN: "采购入库",
    ORDER_TYPE_ADJUST: "库存调整",
    ORDER_TYPE_TRANSFER_OUT: "移库出",
    ORDER_TYPE_TRANSFER_IN: "移库入",
    ORDER_TYPE_STOCK_TAKE: "盘点调整",
}


def order_type_text(order_type: str | None) -> str:
    """单据类型转中文名，未知类型原样返回。"""
    if not order_type:
        return ""
    return ORDER_TYPE_TEXT.get(order_type, order_type)


def _to_decimal(value) -> Decimal:
    """任意数值转 Decimal 并保留 2 位小数。"""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _fmt_qty(value: Decimal) -> str:
    """数量转展示文本，去掉多余的 0（20.00 -> 20，20.50 -> 20.5）。"""
    return format(_to_decimal(value).normalize(), "f")


def merge_changes(changes: list[dict] | None) -> dict[tuple[int, int], Decimal]:
    """要求 1：去重合并。

    同一个 (sku_id, warehouse_id) 出现多行时先在内存里合并成一个变更量，
    合并后为 0 的直接丢掉（不需要动库存、也不需要写流水）。
    """
    merged: dict[tuple[int, int], Decimal] = {}
    for change in changes or []:
        sku_id = int(change["sku_id"])
        warehouse_id = int(change["warehouse_id"])
        quantity = _to_decimal(change.get("quantity"))
        key = (sku_id, warehouse_id)
        merged[key] = merged.get(key, Decimal("0.00")) + quantity
    return {key: value for key, value in merged.items() if value != 0}


def _inventory_condition(keys: list[tuple[int, int]]):
    """构造 (sku_id, warehouse_id) 多行匹配条件。"""
    return or_(
        *[
            and_(Inventory.sku_id == sku_id, Inventory.warehouse_id == warehouse_id)
            for sku_id, warehouse_id in keys
        ]
    )


def _ensure_rows_exist(db: Session, keys: list[tuple[int, int]]) -> None:
    """要求 2：懒创建。

    库存行不存在时直接尝试插入 quantity=0 的记录（不做「先查后插」，那有竞态），
    用 savepoint 包住：唯一键冲突（IntegrityError）时只回滚这个 savepoint，
    外层事务依然可用，说明别的并发事务已经建好了，忽略即可。
    """
    for sku_id, warehouse_id in keys:
        try:
            with db.begin_nested():
                db.add(
                    Inventory(
                        sku_id=sku_id,
                        warehouse_id=warehouse_id,
                        quantity=Decimal("0.00"),
                        reserved_quantity=Decimal("0.00"),
                    )
                )
        except IntegrityError:
            # 库存行已存在，继续走后面的批量加锁查询
            continue


def _lock_rows(db: Session, keys: list[tuple[int, int]]) -> dict[tuple[int, int], Inventory]:
    """要求 3：批量悲观锁。

    收集所有库存行后**一次性** SELECT ... FOR UPDATE 锁定，
    绝不在循环里逐行加锁（会死锁）。

    `order_by(sku_id, warehouse_id)` 是为了把加锁顺序**显式固定**下来：
    否则 InnoDB 按实际扫描顺序加锁，两个访问路径不同的事务可能以相反顺序拿到锁。
    排序后，任何两个涉及同一批 key 的事务都按同一顺序加锁，从根上避免交叉等待。
    """
    rows = db.scalars(
        select(Inventory)
        .where(_inventory_condition(keys))
        .order_by(Inventory.sku_id, Inventory.warehouse_id)
        .with_for_update()
    ).all()
    return {(row.sku_id, row.warehouse_id): row for row in rows}


def _load_locked_rows(
    db: Session, keys: list[tuple[int, int]]
) -> dict[tuple[int, int], Inventory]:
    """懒创建 + 一次性批量加锁，返回 {(sku_id, warehouse_id): Inventory}。

    `change_inventory` / `reserve_inventory` / `release_inventory` 共用这一套流程，
    保证三个入口的并发行为完全一致：先 savepoint 懒创建，再批量 FOR UPDATE 加锁。
    """
    # 要求 2：懒创建缺失的库存行
    _ensure_rows_exist(db, keys)

    # 要求 3：一次性批量加锁
    locked = _lock_rows(db, keys)
    missing = [key for key in keys if key not in locked]
    if missing:
        raise BizException("库存记录初始化失败，请稍后重试")
    return locked


def _load_names(
    db: Session, keys: list[tuple[int, int]]
) -> tuple[dict[int, ProductSku], dict[int, Warehouse]]:
    """批量取 SKU 与仓库，仅用于拼装校验报错信息。"""
    sku_ids = {key[0] for key in keys}
    warehouse_ids = {key[1] for key in keys}
    skus = {
        sku.id: sku for sku in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))
    }
    warehouses = {
        warehouse.id: warehouse
        for warehouse in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))
    }
    return skus, warehouses


def _shortage_text(
    sku_text: str | None, warehouse_text: str | None, available: Decimal, required: Decimal
) -> str:
    """拼装库存不足提示：SKU 编码、仓库名、当前可用量、需求量。"""
    return (
        f"{sku_text or '未知 SKU'} 在{warehouse_text or '未知仓库'}的可用库存为 "
        f"{_fmt_qty(available)}，本次需要 {_fmt_qty(required)}，库存不足"
    )


def check_available(db: Session, changes: list[dict] | None) -> list[dict]:
    """发货 / 出库前的库存预校验（只读，不加锁）。

    返回不足的明细列表，元素结构：
        {sku_id, sku_code, warehouse_id, warehouse_name,
         available_quantity, required_quantity, shortage_quantity}
    全部充足时返回空列表。
    """
    merged = merge_changes(changes)
    # 只有出库（负数）才需要校验可用量
    needs = {key: -value for key, value in merged.items() if value < 0}
    if not needs:
        return []

    keys = sorted(needs.keys())
    rows = db.scalars(select(Inventory).where(_inventory_condition(keys))).all()
    inventory_map = {(row.sku_id, row.warehouse_id): row for row in rows}
    skus, warehouses = _load_names(db, keys)

    shortages: list[dict] = []
    for key in keys:
        row = inventory_map.get(key)
        if row is None:
            available = Decimal("0.00")
        else:
            available = _to_decimal(row.quantity) - _to_decimal(row.reserved_quantity)
        required = needs[key]
        if available < required:
            sku = skus.get(key[0])
            warehouse = warehouses.get(key[1])
            shortages.append(
                {
                    "sku_id": key[0],
                    "sku_code": sku.sku_code if sku else None,
                    "warehouse_id": key[1],
                    "warehouse_name": warehouse.name if warehouse else None,
                    "available_quantity": available,
                    "required_quantity": required,
                    "shortage_quantity": required - available,
                }
            )
    return shortages


def shortage_message(shortages: list[dict]) -> str:
    """把 check_available 的结果拼成一句友好的报错文案。"""
    return "；".join(
        _shortage_text(
            item.get("sku_code"),
            item.get("warehouse_name"),
            _to_decimal(item.get("available_quantity")),
            _to_decimal(item.get("required_quantity")),
        )
        for item in shortages
    )


def lock_inventory_keys(db: Session, changes: list[dict] | None) -> None:
    """按全局有序顺序**预先**锁定一批库存行（供跨多次 `change_inventory` 调用的场景）。

    为什么需要它：移库要同时改「出库仓 -N」和「入库仓 +N」，最直观的写法是调两次
    `change_inventory`。但每次调用内部只对自己的 key 排序，**两次调用之间的加锁顺序
    不保证一致**。于是两张方向相反的移库单（A→B 与 B→A）携带重叠 SKU 并发执行时：

        T1 持有 (sku,A) 等 (sku,B)
        T2 持有 (sku,B) 等 (sku,A)   ← ABBA 死锁，InnoDB 报 1213

    解决方式：在两次调用之前，把涉及的 `(sku_id, warehouse_id)` 全部合并后
    按同一个全局顺序一次性锁住。后续 `change_inventory` 内部的加锁就变成
    同一事务内的重复加锁（幂等），不再产生交叉等待。

    本函数不提交事务，由调用方 commit；只加锁、不改数量、不写流水。
    """
    keys = sorted(merge_changes(changes).keys())
    if not keys:
        return
    _load_locked_rows(db, keys)


def change_inventory(
    db: Session,
    changes: list[dict],
    order_no: str,
    order_type: str,
    operator_id: int,
    remark: str | None = None,
) -> None:
    """库存变更统一入口（契约 9.3）。

    :param changes: [{"sku_id": 1, "warehouse_id": 1, "quantity": 10}]，正数入库、负数出库
    :param order_no: 关联单号，写入库存流水
    :param order_type: SALES_OUT / PURCHASE_IN / ADJUST
    :param operator_id: 操作人 user_id
    :param remark: 备注（如盘点说明），写入库存流水，可空

    不提交事务，由调用方 commit。
    """
    merged = merge_changes(changes)
    if not merged:
        return

    # 排序保证加锁顺序一致，进一步降低死锁概率
    keys = sorted(merged.keys())

    # 要求 2 + 3：懒创建缺失的库存行，再一次性批量加锁
    locked = _load_locked_rows(db, keys)

    # 要求 4：出库校验，不足则抛业务异常（code=1001）
    outbound_keys = [key for key in keys if merged[key] < 0]
    if outbound_keys:
        # 只有出库才需要 SKU / 仓库名来拼报错文案，避免纯入库时多查两次
        skus, warehouses = _load_names(db, outbound_keys)
        for key in outbound_keys:
            row = locked[key]
            available = _to_decimal(row.quantity) - _to_decimal(row.reserved_quantity)
            required = -merged[key]
            if available < required:
                raise BizException(
                    _shortage_text(
                        skus.get(key[0]).sku_code if key[0] in skus else None,
                        warehouses.get(key[1]).name if key[1] in warehouses else None,
                        available,
                        required,
                    )
                )

    # 要求 5：更新库存 + 逐笔写流水
    for key in keys:
        delta = merged[key]
        row = locked[key]
        before = _to_decimal(row.quantity)
        after = before + delta
        row.quantity = after
        db.add(
            InventoryHistory(
                sku_id=key[0],
                warehouse_id=key[1],
                quantity=delta,
                before_quantity=before,
                after_quantity=after,
                order_no=order_no,
                order_type=order_type,
                created_by=operator_id,
                remark=remark,
            )
        )


def _apply_reserved(
    db: Session,
    changes: list[dict] | None,
    order_no: str,
    operator_id: int,
    direction: int,
) -> list[dict]:
    """预留 / 释放预留的公共实现：只动 `reserved_quantity`。

    与 `change_inventory` 一样：去重合并 → 懒创建（savepoint 兜并发）→ 批量
    `SELECT ... FOR UPDATE` 加锁 → 校验 → 更新，**内部不 commit**，由调用方统一提交。

    注意：这里取变更量的**绝对值**，符号不参与判断。调用方可以直接把出库用的
    changes（负数）原样传进来，不用再取反，避免预留量与释放量对不上。

    :param direction: +1 预留（增加预留量），-1 释放（减少预留量）
    :return: 释放预留时出现的「预留量不足以释放」告警明细列表，正常情况为空列表
    """
    merged = merge_changes(changes)
    if not merged:
        return []

    # 排序保证加锁顺序一致，进一步降低死锁概率
    keys = sorted(merged.keys())
    locked = _load_locked_rows(db, keys)

    # 校验报错 / 钳制告警都要带 SKU 编码与仓库名，一次性批量取
    skus, warehouses = _load_names(db, keys)

    # 要求（契约 12.3 + P1-2）：预留必须在**加锁之后**校验可用量。
    # 外层 check_available 是无锁只读查询，并发接单时会同时通过，导致同一批货被预留两次。
    if direction > 0:
        for key in keys:
            row = locked[key]
            available = _to_decimal(row.quantity) - _to_decimal(row.reserved_quantity)
            required = abs(merged[key])
            if available < required:
                sku = skus.get(key[0])
                warehouse = warehouses.get(key[1])
                raise BizException(
                    _shortage_text(
                        sku.sku_code if sku else None,
                        warehouse.name if warehouse else None,
                        available,
                        required,
                    )
                )

    warnings: list[dict] = []
    for key in keys:
        row = locked[key]
        amount = abs(merged[key])
        before = _to_decimal(row.reserved_quantity)
        after = before + amount * direction
        if after < 0:
            # 释放量大于当前预留量：说明数据不一致（例如同一订单被重复释放）。
            # 这里钳制到 0 而不抛异常，避免因为历史脏数据导致取消订单 / 发货失败；
            # 差异以 warning 日志 + 返回值暴露给调用方，便于排查（P2-2）。
            sku = skus.get(key[0])
            warehouse = warehouses.get(key[1])
            warnings.append(
                {
                    "order_no": order_no,
                    "sku_id": key[0],
                    "sku_code": sku.sku_code if sku else None,
                    "warehouse_id": key[1],
                    "warehouse_name": warehouse.name if warehouse else None,
                    "before_reserved": before,
                    "release_amount": amount,
                    "operator_id": operator_id,
                }
            )
            logger.warning(
                "释放预留库存超过当前预留量，已钳制为 0（库存预留账实不符）："
                "order_no=%s, sku_code=%s, warehouse=%s, 释放前预留=%s, 本次释放量=%s, operator_id=%s",
                order_no,
                sku.sku_code if sku else key[0],
                warehouse.name if warehouse else key[1],
                _fmt_qty(before),
                _fmt_qty(amount),
                operator_id,
            )
            after = Decimal("0.00")
        row.reserved_quantity = after

    # 会话是 autoflush=False，这里显式 flush：
    # 保证同一事务内后续的 SELECT（如 check_available、change_inventory 的加锁查询）
    # 能读到最新的预留量，也保证预留先于出库单 savepoint 落库、不会被 savepoint 回滚。
    db.flush()
    return warnings


def reserve_inventory(
    db: Session,
    changes: list[dict],
    order_no: str,
    operator_id: int,
) -> None:
    """预留库存：只增加 `reserved_quantity`，不改 `quantity`，不写库存流水（预留不是库存变动）。

    **可用量校验在加锁之后进行**（契约 12.3）：不足时抛业务异常（code=1001），
    错误信息带 SKU 编码、仓库名、当前可用量、需求量。

    :param changes: [{"sku_id": 1, "warehouse_id": 1, "quantity": 10}]，取数量绝对值作为预留量
    :param order_no: 关联单号，仅用于日志排查
    :param operator_id: 操作人 user_id，仅用于日志排查

    不提交事务，由调用方 commit。
    """
    _apply_reserved(db, changes, order_no, operator_id, direction=1)


def release_inventory(
    db: Session,
    changes: list[dict],
    order_no: str,
    operator_id: int,
) -> list[dict]:
    """释放预留：减少 `reserved_quantity`。释放量不得使 `reserved_quantity` 为负。

    若释放量会导致 `reserved_quantity` 为负，**钳制到 0** 并写 warning 日志，
    不抛异常——避免因为数据不一致导致取消订单 / 发货失败。这里选择「告警而非抛异常」，
    是因为取消订单 / 发货是业务闭环的必经动作，抛异常会让订单卡死；同时通过返回值把
    不一致明细交回调用方，让问题可观测、可排查（P2-2）。

    :param changes: 与 `change_inventory` 同格式，取数量绝对值作为释放量
    :param order_no: 关联单号，仅用于日志排查
    :param operator_id: 操作人 user_id，仅用于日志排查
    :return: 预留量不足以释放的告警明细列表（已钳制为 0），正常情况为空列表

    不提交事务，由调用方 commit。
    """
    return _apply_reserved(db, changes, order_no, operator_id, direction=-1)
