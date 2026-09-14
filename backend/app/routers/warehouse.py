from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import SentryAdapterError, SentryWMSAdapter, get_sentry_adapter
from app.constants import STATUS_IN_PROGRESS, STATUS_SKU_CONFIRM, STATUS_WAREHOUSE_REVIEW
from app.db import get_db
from app.deps import require_wms_token
from app.models import Sku, SkuReviewLog, SubmissionLine, SubmissionOrder
from app.schemas import (
    ChangeLineItemRequest,
    MergeDuplicateRequest,
    VerifySubmissionRequest,
    WarehouseCancelOrderRequest,
)
from app.services import (
    all_lines_active,
    audit_submission,
    get_submission,
    make_draft_for_line,
    maybe_complete_submission,
    now_utc,
    reset_timer,
    serialize_submission,
)


router = APIRouter(
    prefix="/warehouse", tags=["warehouse"], dependencies=[Depends(require_wms_token)]
)


@router.get("/submissions")
async def warehouse_submissions(status: int | None = None, session: AsyncSession = Depends(get_db)):
    stmt = select(SubmissionOrder.submission_id).distinct()
    ids = list((await session.scalars(stmt)).all())
    records = []
    for submission_id in ids:
        submission = await get_submission(session, submission_id)
        if status is None or submission.status == status:
            records.append(serialize_submission(submission))
    return records


@router.post("/submissions/{submission_id}/verify")
async def verify_submission(
    submission_id: int,
    body: VerifySubmissionRequest,
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.status != STATUS_WAREHOUSE_REVIEW:
        raise HTTPException(status_code=409, detail="当前状态不能执行仓库核验")
    if any(order.confirm_status == "rejected" for order in submission.orders):
        raise HTTPException(status_code=409, detail="驳回批次请使用 rework 接口处理")
    names = {item.line_id: item.item_name.strip() for item in body.new_items}
    all_lines = [line for order in submission.orders for line in order.lines]
    if not set(names).issubset({line.id for line in all_lines}):
        raise HTTPException(status_code=422, detail="new_items 包含不属于本批次的明细行")
    for line in all_lines:
        if line.is_new_item and line.item_id is None:
            item_name = names.get(line.id)
            if not item_name:
                raise HTTPException(status_code=422, detail=f"新品行 {line.id} 必须填写正式商品名")
            await make_draft_for_line(session, line, item_name, "warehouse")
        elif not line.is_new_item:
            if line.item is None or line.item.code_status != "active" or not line.item.is_active:
                raise HTTPException(status_code=422, detail=f"明细行 {line.id} 的货号无效")
    reset_timer(submission, status=STATUS_SKU_CONFIRM)
    audit_submission(session, submission, "warehouse_verify", "warehouse", None)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/skus/{sku_id}/promote")
async def promote_sku(
    sku_id: int,
    session: AsyncSession = Depends(get_db),
    adapter: SentryWMSAdapter = Depends(get_sentry_adapter),
):
    sku = await session.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="货号不存在")
    if sku.code_status == "active":
        return {"sku_id": sku.id, "code_status": sku.code_status, "replayed": True}
    sku.code_status = "active"
    sku.promoted_at = now_utc()
    await session.flush()
    try:
        await adapter.push_item(sku)
    except SentryAdapterError as exc:
        await session.rollback()
        raise HTTPException(status_code=502, detail=str(exc))
    lines = list(
        (await session.scalars(select(SubmissionLine).where(SubmissionLine.item_id == sku.id))).all()
    )
    for line in lines:
        session.add(
            SkuReviewLog(
                submission_line_id=line.id,
                action="promote",
                from_sku_id=sku.id,
                to_sku_id=sku.id,
                draft_sku_code=sku.sku_code,
                operator="warehouse",
            )
        )
    await session.commit()
    return {"sku_id": sku.id, "code_status": sku.code_status, "replayed": False}


@router.post("/submissions/{submission_id}/lines/{line_id}/change-item")
async def change_line_item(
    submission_id: int,
    line_id: int,
    body: ChangeLineItemRequest,
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.status != STATUS_WAREHOUSE_REVIEW:
        raise HTTPException(status_code=409, detail="货号确认后不能再改号")
    line = next(
        (line for order in submission.orders for line in order.lines if line.id == line_id), None
    )
    if line is None:
        raise HTTPException(status_code=404, detail="明细行不存在")
    if line.is_new_item:
        raise HTTPException(status_code=409, detail="新品行判重请使用 merge-duplicate 接口")
    target = await session.get(Sku, body.item_id)
    if target is None or target.code_status != "active" or not target.is_active:
        raise HTTPException(status_code=422, detail="只能改为启用的正式货号")
    old_id = line.item_id
    line.item_id = target.id
    line.item_desc = target.item_name
    session.add(
        SkuReviewLog(
            submission_line_id=line.id,
            action="change_item",
            from_sku_id=old_id,
            to_sku_id=target.id,
            operator="warehouse",
        )
    )
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/submissions/{submission_id}/lines/{line_id}/merge-duplicate")
async def merge_duplicate(
    submission_id: int,
    line_id: int,
    body: MergeDuplicateRequest,
    session: AsyncSession = Depends(get_db),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.status not in {STATUS_WAREHOUSE_REVIEW, STATUS_SKU_CONFIRM}:
        raise HTTPException(status_code=409, detail="当前状态不能执行判重")
    line = next(
        (line for order in submission.orders for line in order.lines if line.id == line_id), None
    )
    if line is None or line.item is None or line.item.code_status != "draft":
        raise HTTPException(status_code=409, detail="该行没有可判重删除的待审核货号")
    target = await session.get(Sku, body.existing_item_id)
    if target is None or target.code_status != "active" or not target.is_active:
        raise HTTPException(status_code=422, detail="重复品目标必须是启用的正式货号")
    draft = line.item
    draft_id = draft.id
    draft_code = draft.sku_code
    line.item_id = target.id
    line.is_new_item = False
    line.category_id = None
    line.draft_sku_code = draft_code
    session.add(
        SkuReviewLog(
            submission_line_id=line.id,
            action="merge_duplicate",
            from_sku_id=draft_id,
            to_sku_id=target.id,
            draft_sku_code=draft_code,
            operator="warehouse",
        )
    )
    await session.flush()
    await session.delete(draft)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/submissions/{submission_id}/rework")
async def finish_rework(submission_id: int, session: AsyncSession = Depends(get_db)):
    submission = await get_submission(session, submission_id, for_update=True)
    rejected = [order for order in submission.orders if order.confirm_status == "rejected"]
    if submission.status != STATUS_WAREHOUSE_REVIEW or not rejected:
        raise HTTPException(status_code=409, detail="当前批次没有待返工订单")
    if not await all_lines_active(session, submission):
        raise HTTPException(status_code=409, detail="返工后仍存在未转正或停用货号")
    for order in rejected:
        order.confirm_status = "pending"
        for line in order.lines:
            line.line_status = "pending"
            line.reject_reason = None
    reset_timer(submission, status=STATUS_SKU_CONFIRM)
    audit_submission(session, submission, "warehouse_rework", "warehouse", None)
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/submissions/{submission_id}/dispatch")
async def dispatch_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_db),
    adapter: SentryWMSAdapter = Depends(get_sentry_adapter),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.status != 4:
        raise HTTPException(status_code=409, detail="只有状态 4 可以向 sentry-wms 下单")
    failures = []
    for order in submission.orders:
        if order.status != "pending":
            continue
        try:
            result = await adapter.create_sales_order(submission, order)
        except SentryAdapterError as exc:
            failures.append({"order_id": order.id, "error": str(exc)})
            continue
        canonical_id = result.get("canonical_id")
        if canonical_id:
            try:
                order.wms_canonical_id = UUID(str(canonical_id))
            except ValueError:
                pass
        if isinstance(result.get("sales_order_id"), int):
            order.sales_order_id = result["sales_order_id"]
        order.status = "shortage" if result.get("status") == "BACKORDER" else "ordered"
        if order.status == "shortage":
            order.shortage_at = now_utc()
        await session.commit()
    if failures:
        raise HTTPException(status_code=502, detail={"message": "部分订单下单失败，批次保持状态 4", "failures": failures})
    submission = await get_submission(session, submission_id)
    if all(order.status in {"ordered", "shortage"} for order in submission.orders):
        reset_timer(submission, status=STATUS_IN_PROGRESS)
        audit_submission(session, submission, "dispatch", "system", None)
        await session.commit()
    return serialize_submission(await get_submission(session, submission.id))


@router.post("/submissions/{submission_id}/orders/{order_id}/cancel")
async def warehouse_cancel_order(
    submission_id: int,
    order_id: int,
    body: WarehouseCancelOrderRequest,
    session: AsyncSession = Depends(get_db),
    adapter: SentryWMSAdapter = Depends(get_sentry_adapter),
):
    submission = await get_submission(session, submission_id, for_update=True)
    if submission.status != STATUS_IN_PROGRESS:
        raise HTTPException(status_code=409, detail="只有作业中且未发货的订单可截单")
    order = next((value for value in submission.orders if value.id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in {"ordered", "shortage"}:
        raise HTTPException(status_code=409, detail="该订单已发货或已取消")
    try:
        await adapter.cancel_sales_order(order, body.reason)
    except SentryAdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    order.status = "cancelled"
    maybe_complete_submission(submission)
    audit_submission(
        session, submission, "warehouse_cancel_order", "warehouse", {"order_id": order.id, "reason": body.reason}
    )
    await session.commit()
    return serialize_submission(await get_submission(session, submission.id))
