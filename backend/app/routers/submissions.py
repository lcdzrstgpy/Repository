from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import STATUS_CANCELLED, STATUS_QTY_CONFIRM, STATUS_SKU_CONFIRM
from app.db import get_db
from app.deps import current_ops_user
from app.models import Sku, Submission, SubmissionLine, SubmissionOrder, User
from app.schemas import (
    CancelRequest,
    QuantityConfirmRequest,
    RejectOrderRequest,
    SubmissionCreate,
)
from app.services import (
    audit_submission,
    get_submission,
    now_utc,
    reset_timer,
    serialize_submission,
)


router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", status_code=201)
async def create_submission(
    body: SubmissionCreate,
    response: Response,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    existing = await session.scalar(
        select(Submission).where(Submission.idempotency_key == body.idempotency_key)
    )
    if existing is not None:
        if existing.submitted_by != user.username:
            raise HTTPException(status_code=409, detail="幂等键已被其他账号使用")
        response.status_code = 200
        return serialize_submission(await get_submission(session, existing.id))

    active_ids = {
        line.item_id
        for order in body.orders
        for line in order.lines
        if not line.is_new_item and line.item_id is not None
    }
    if active_ids:
        rows = list(
            (
                await session.scalars(
                    select(Sku).where(
                        Sku.id.in_(active_ids),
                        Sku.code_status == "active",
                        Sku.is_active.is_(True),
                    )
                )
            ).all()
        )
        if {sku.id for sku in rows} != active_ids:
            raise HTTPException(status_code=422, detail="老品行只能引用启用的正式货号")

    submission = Submission(
        submission_no=f"PENDING-{uuid4()}",
        idempotency_key=body.idempotency_key,
        remark=body.remark,
        submitted_by=user.username,
    )
    for order_data in body.orders:
        order = SubmissionOrder(order_no=order_data.order_no)
        submission.orders.append(order)
        for line_no, line_data in enumerate(order_data.lines, start=1):
            order.lines.append(SubmissionLine(line_no=line_no, **line_data.model_dump()))
    session.add(submission)
    await session.flush()
    submission.submission_no = f"SUB-{now_utc():%Y%m%d}-{submission.id:06d}"
    audit_submission(session, submission, "submit", user.username, None)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.get("")
async def list_submissions(
    status: int | None = Query(default=None, ge=0, le=6),
    order_no: str | None = Query(default=None, max_length=128),
    has_shortage: bool | None = None,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Submission).where(Submission.submitted_by == user.username)
    if status is not None:
        stmt = stmt.where(Submission.status == status)
    if order_no:
        stmt = stmt.join(Submission.orders).where(SubmissionOrder.order_no.ilike(f"%{order_no}%"))
    if has_shortage is not None:
        condition = Submission.orders.any(SubmissionOrder.status == "shortage")
        stmt = stmt.where(condition if has_shortage else ~condition)
    records = list((await session.scalars(stmt.order_by(Submission.submitted_at.desc()))).unique().all())
    return [serialize_submission(await get_submission(session, item.id)) for item in records]


@router.get("/{submission_id}")
async def submission_detail(
    submission_id: int,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id)
    if submission.submitted_by != user.username:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    return serialize_submission(submission)


@router.post("/{submission_id}/confirm-items")
async def confirm_items(
    submission_id: int,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.submitted_by != user.username:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    if submission.status != STATUS_SKU_CONFIRM:
        raise HTTPException(status_code=409, detail="当前状态不能确认货号")
    if any(order.confirm_status == "rejected" for order in submission.orders):
        raise HTTPException(status_code=409, detail="仍有被驳回订单待仓库处理")
    items = [line.item for order in submission.orders for line in order.lines]
    if any(item is None or item.code_status != "active" or not item.is_active for item in items):
        raise HTTPException(status_code=409, detail="存在未转正或停用货号")
    for order in submission.orders:
        if order.confirm_status == "pending":
            order.confirm_status = "confirmed"
        for line in order.lines:
            line.line_status = "confirmed"
            line.reject_reason = None
    reset_timer(submission, status=STATUS_QTY_CONFIRM)
    audit_submission(session, submission, "confirm_items", user.username, None)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/{submission_id}/orders/{order_id}/reject")
async def reject_order(
    submission_id: int,
    order_id: int,
    body: RejectOrderRequest,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.submitted_by != user.username:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    if submission.status != STATUS_SKU_CONFIRM:
        raise HTTPException(status_code=409, detail="当前状态不能驳回")
    order = next((value for value in submission.orders if value.id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.reject_count >= 3:
        raise HTTPException(status_code=409, detail="该订单已达到最多 3 次驳回限制")
    if order.confirm_status == "rejected":
        raise HTTPException(status_code=409, detail="该订单已处于驳回处理中")
    order.confirm_status = "rejected"
    order.reject_count += 1
    for line in order.lines:
        line.line_status = "rejected"
        line.reject_reason = body.reason
    reset_timer(submission, status=1)
    audit_submission(
        session,
        submission,
        "reject_order",
        user.username,
        {"order_id": order.id, "reason": body.reason, "reject_count": order.reject_count},
    )
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/{submission_id}/confirm-quantities")
async def confirm_quantities(
    submission_id: int,
    body: QuantityConfirmRequest,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.submitted_by != user.username:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    if submission.status != STATUS_QTY_CONFIRM:
        raise HTTPException(status_code=409, detail="当前状态不能提交数量，数量可能已锁定")
    lines = [line for order in submission.orders for line in order.lines]
    supplied = {item.line_id: item.qty for item in body.quantities}
    if set(supplied) != {line.id for line in lines}:
        raise HTTPException(status_code=422, detail="必须一次提交批次内全部明细行数量")
    locked_at = now_utc()
    for line in lines:
        if line.qty_locked_at is not None:
            raise HTTPException(status_code=409, detail="数量已锁定")
        line.qty = supplied[line.id]
        line.qty_locked_at = locked_at
    reset_timer(submission, status=4)
    audit_submission(session, submission, "confirm_quantities", user.username, None)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/{submission_id}/cancel")
async def cancel_submission(
    submission_id: int,
    body: CancelRequest,
    user: User = Depends(current_ops_user),
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.submitted_by != user.username:
        raise HTTPException(status_code=404, detail="提交批次不存在")
    if submission.status not in {1, 2, 3}:
        raise HTTPException(status_code=409, detail="运营只能取消状态 1–3 的批次")
    submission.status = STATUS_CANCELLED
    submission.cancelled_at = now_utc()
    submission.cancel_reason = body.reason
    submission.status_entered_at = now_utc()
    for order in submission.orders:
        order.status = "cancelled"
    audit_submission(session, submission, "cancel", user.username, body.reason)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))
