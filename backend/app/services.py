from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ORDER_TERMINAL_STATUSES, STATUS_COMPLETED, STATUS_IN_PROGRESS
from app.models import (
    Category,
    ShipmentPackage,
    Sku,
    SkuReviewLog,
    Submission,
    SubmissionAuditLog,
    SubmissionLine,
    SubmissionOrder,
    User,
)
from app.security import hash_password


DEFAULT_CATEGORIES = {
    "家居用品": [("杯具", "A001"), ("餐具", "A002"), ("收纳", "A003")],
    "厨房用品": [("锅具", "B001"), ("小家电", "B002")],
    "日用百货": [("清洁用品", "C001"), ("纸品", "C002")],
    "服饰配件": [("帽子", "D001"), ("围巾", "D002")],
    "宠物用品": [("食具", "E001"), ("玩具", "E002")],
    "文具": [("笔类", "F001"), ("本册", "F002")],
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def get_submission(
    session: AsyncSession, submission_id: int, *, for_update: bool = False
) -> Submission:
    stmt = (
        select(Submission)
        .where(Submission.id == submission_id)
        .options(
            selectinload(Submission.orders)
            .selectinload(SubmissionOrder.lines)
            .selectinload(SubmissionLine.item),
            selectinload(Submission.orders).selectinload(SubmissionOrder.packages),
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    submission = await session.scalar(stmt)
    if submission is None:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    return submission


def reset_timer(submission: Submission, *, status: int | None = None) -> None:
    if status is not None:
        submission.status = status
    submission.status_entered_at = now_utc()
    submission.alert_1h_at = None
    submission.alert_2h_at = None


def timeout_responsibility(submission: Submission) -> str | None:
    if submission.status == 1:
        return "warehouse"
    if submission.status == 2:
        if any(order.confirm_status == "rejected" for order in submission.orders):
            return "warehouse"
        return "ops"
    if submission.status == 3:
        return "ops"
    if submission.status == 4:
        return "warehouse"
    return None


async def scan_timeouts(session: AsyncSession) -> list[dict]:
    """1h 提醒责任方、2h 两侧同时提醒；按 status_entered_at 分环节独立计时。"""
    now = now_utc()
    records = list(
        (
            await session.scalars(
                select(Submission)
                .where(Submission.status.in_([1, 2, 3, 4]))
                .options(selectinload(Submission.orders))
            )
        ).all()
    )
    alerts: list[dict] = []
    for submission in records:
        entered = submission.status_entered_at
        if entered.tzinfo is None:
            entered = entered.replace(tzinfo=timezone.utc)
        age = now - entered
        if age >= timedelta(hours=2):
            if submission.alert_2h_at is None:
                submission.alert_2h_at = now
                alerts.append(
                    {
                        "submission_id": submission.id,
                        "level": 2,
                        "recipients": ["ops", "warehouse"],
                    }
                )
        elif age >= timedelta(hours=1) and submission.alert_1h_at is None:
            submission.alert_1h_at = now
            alerts.append(
                {
                    "submission_id": submission.id,
                    "level": 1,
                    "recipients": [timeout_responsibility(submission)],
                }
            )
    await session.commit()
    return alerts


def serialize_submission(submission: Submission) -> dict:
    now = now_utc()
    entered = submission.status_entered_at
    if entered.tzinfo is None:
        entered = entered.replace(tzinfo=timezone.utc)
    elapsed = max(0, int((now - entered).total_seconds()))
    timeout_level = 2 if elapsed >= 7200 else 1 if elapsed >= 3600 else 0
    return {
        "id": submission.id,
        "submission_no": submission.submission_no,
        "idempotency_key": submission.idempotency_key,
        "status": submission.status,
        "remark": submission.remark,
        "submitted_by": submission.submitted_by,
        "submitted_at": submission.submitted_at,
        "status_entered_at": submission.status_entered_at,
        "timeout_level": timeout_level if submission.status in {1, 2, 3, 4} else 0,
        "responsible_party": timeout_responsibility(submission),
        "completed_at": submission.completed_at,
        "cancelled_at": submission.cancelled_at,
        "cancel_reason": submission.cancel_reason,
        "orders": [
            {
                "id": order.id,
                "order_no": order.order_no,
                "external_id": str(order.external_id),
                "status": order.status,
                "confirm_status": order.confirm_status,
                "reject_count": order.reject_count,
                "sales_order_id": order.sales_order_id,
                "wms_canonical_id": str(order.wms_canonical_id) if order.wms_canonical_id else None,
                "shortage_at": order.shortage_at,
                "picked_at": order.picked_at,
                "packed_at": order.packed_at,
                "shipped_at": order.shipped_at,
                "lines": [
                    {
                        "id": line.id,
                        "line_no": line.line_no,
                        "item_id": line.item_id,
                        "sku_code": line.item.sku_code if line.item else None,
                        "item_name": line.item.item_name if line.item else None,
                        "item_desc": line.item_desc,
                        "is_new_item": line.is_new_item,
                        "category_id": line.category_id,
                        "draft_sku_code": line.draft_sku_code,
                        "qty": line.qty,
                        "qty_locked_at": line.qty_locked_at,
                        "line_status": line.line_status,
                        "reject_reason": line.reject_reason,
                    }
                    for line in sorted(order.lines, key=lambda value: value.line_no)
                ],
                "packages": [
                    {
                        "package_external_id": package.package_external_id,
                        "carrier": package.carrier,
                        "service_level": package.service_level,
                        "tracking_number": package.tracking_number,
                    }
                    for package in order.packages
                ],
            }
            for order in order_by_id(submission.orders)
        ],
    }


def order_by_id(orders: list[SubmissionOrder]) -> list[SubmissionOrder]:
    return sorted(orders, key=lambda value: value.id or 0)


async def generate_sku_code(session: AsyncSession, category_id: int) -> tuple[Category, str]:
    if session.bind and session.bind.dialect.name == "postgresql":
        row = (
            await session.execute(
                text(
                    "UPDATE hub.category SET seq_counter = seq_counter + 1 "
                    "WHERE id = :category_id AND parent_id IS NOT NULL "
                    "AND is_active = TRUE AND code_prefix IS NOT NULL "
                    "RETURNING id, category_name, code_prefix, seq_counter"
                ),
                {"category_id": category_id},
            )
        ).mappings().first()
        if row is None:
            raise HTTPException(status_code=422, detail="category_id 必须是有效的二级类目")
        category = await session.get(Category, category_id)
        return category, f"{row['code_prefix']}-{row['seq_counter']}"

    category = await session.scalar(
        select(Category).where(Category.id == category_id).with_for_update()
    )
    if (
        category is None
        or category.parent_id is None
        or not category.is_active
        or not category.code_prefix
    ):
        raise HTTPException(status_code=422, detail="category_id 必须是有效的二级类目")
    category.seq_counter += 1
    await session.flush()
    return category, f"{category.code_prefix}-{category.seq_counter}"


async def create_sku(
    session: AsyncSession,
    *,
    category_id: int,
    item_name: str,
    code_status: str,
    spec_name: str | None = None,
    barcode: str | None = None,
    weight=None,
    length=None,
    width=None,
    height=None,
) -> Sku:
    _, sku_code = await generate_sku_code(session, category_id)
    sku = Sku(
        sku_code=sku_code,
        category_id=category_id,
        item_name=item_name.strip(),
        code_status=code_status,
        spec_name=spec_name,
        barcode=barcode,
        promoted_at=now_utc() if code_status == "active" else None,
    )
    session.add(sku)
    await session.flush()
    return sku


async def make_draft_for_line(
    session: AsyncSession, line: SubmissionLine, item_name: str, operator: str
) -> Sku:
    if not line.is_new_item or line.category_id is None:
        raise HTTPException(status_code=422, detail=f"明细行 {line.id} 不是新品行")
    if line.item_id is not None:
        return line.item
    sku = await create_sku(
        session,
        category_id=line.category_id,
        item_name=item_name,
        code_status="draft",
    )
    line.item_id = sku.id
    line.draft_sku_code = sku.sku_code
    session.add(
        SkuReviewLog(
            submission_line_id=line.id,
            action="create_draft",
            to_sku_id=sku.id,
            draft_sku_code=sku.sku_code,
            operator=operator,
        )
    )
    return sku


async def all_lines_active(session: AsyncSession, submission: Submission) -> bool:
    item_ids = [line.item_id for order in submission.orders for line in order.lines]
    if not item_ids or any(item_id is None for item_id in item_ids):
        return False
    unique_item_ids = set(item_ids)
    count = await session.scalar(
        select(func.count(Sku.id)).where(
            Sku.id.in_(unique_item_ids), Sku.code_status == "active", Sku.is_active.is_(True)
        )
    )
    return count == len(unique_item_ids)


def maybe_complete_submission(submission: Submission) -> None:
    if submission.status == STATUS_IN_PROGRESS and submission.orders and all(
        order.status in ORDER_TERMINAL_STATUSES for order in submission.orders
    ):
        submission.status = STATUS_COMPLETED
        submission.completed_at = now_utc()
        submission.status_entered_at = now_utc()


def audit_submission(
    session: AsyncSession, submission: Submission, action: str, operator: str, detail: dict | str | None
) -> None:
    value = json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail
    session.add(
        SubmissionAuditLog(
            submission_id=submission.id, action=action, operator=operator, detail=value
        )
    )


async def seed_reference_data(
    session: AsyncSession,
    *,
    seed_categories: bool,
    username: str | None,
    password: str | None,
) -> None:
    if seed_categories and not await session.scalar(select(func.count(Category.id))):
        for root_name, children in DEFAULT_CATEGORIES.items():
            root = Category(category_name=root_name)
            session.add(root)
            await session.flush()
            for child_name, prefix in children:
                session.add(
                    Category(
                        category_name=child_name,
                        parent_id=root.id,
                        code_prefix=prefix,
                    )
                )
    if username and password:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is None:
            session.add(
                User(username=username, password_hash=hash_password(password), role="ops")
            )
    await session.commit()
