from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.constants import SUPPORTED_WEBHOOK_EVENTS
from app.db import get_db
from app.models import (
    InventoryLedger,
    ShipmentPackage,
    Sku,
    Submission,
    SubmissionLine,
    SubmissionOrder,
    WebhookDedup,
)
from app.schemas import WebhookEnvelope
from app.services import maybe_complete_submission, now_utc


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_hmac(body: bytes, timestamp: int, signature: str, secret: str) -> bool:
    # 与 sentry-wms（Apache-2.0）的 timestamp + "." + raw-body 线协议兼容；此处为独立实现。
    canonical = f"{timestamp}.".encode("ascii") + body
    expected = "sha256=" + hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_event_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return now_utc()


def event_external_ids(envelope: WebhookEnvelope) -> list[UUID]:
    data = envelope.data
    values = [
        data.get("sales_order_external_id"),
        data.get("backorder_so_external_id"),
        data.get("parent_so_external_id"),
        envelope.aggregate_id,
    ]
    result = []
    for value in values:
        if value is None:
            continue
        try:
            parsed = UUID(str(value))
        except ValueError:
            continue
        if parsed not in result:
            result.append(parsed)
    return result


async def find_submission_order(
    session: AsyncSession, envelope: WebhookEnvelope
) -> tuple[Submission, SubmissionOrder] | None:
    ids = event_external_ids(envelope)
    if not ids:
        return None
    submission = await session.scalar(
        select(Submission)
        .join(Submission.orders)
        .where(
            or_(
                SubmissionOrder.external_id.in_(ids),
                SubmissionOrder.wms_canonical_id.in_(ids),
            )
        )
        .with_for_update()
        .options(
            selectinload(Submission.orders)
            .selectinload(SubmissionOrder.lines)
            .selectinload(SubmissionLine.item),
            selectinload(Submission.orders).selectinload(SubmissionOrder.packages),
        )
    )
    if submission is None:
        return None
    order = next(
        (
            value
            for value in submission.orders
            if value.external_id in ids or value.wms_canonical_id in ids
        ),
        None,
    )
    return (submission, order) if order else None


async def append_ledger(
    session: AsyncSession,
    *,
    sku: Sku,
    bin_external_id: UUID | None,
    bin_id: int | None,
    warehouse_id: int,
    delta: int,
    source_type: str,
    source_id: int,
    operator: str | None,
) -> None:
    stmt = select(InventoryLedger).where(InventoryLedger.sku_id == sku.id)
    if bin_external_id is None:
        stmt = stmt.where(InventoryLedger.bin_external_id.is_(None))
    else:
        stmt = stmt.where(InventoryLedger.bin_external_id == bin_external_id)
    previous = await session.scalar(stmt.order_by(InventoryLedger.id.desc()).limit(1))
    session.add(
        InventoryLedger(
            sku_id=sku.id,
            bin_id=bin_id,
            bin_external_id=bin_external_id,
            warehouse_id=warehouse_id,
            delta=delta,
            balance_after=(previous.balance_after if previous else 0) + delta,
            source_type=source_type,
            source_id=source_id,
            operator=operator,
        )
    )


async def process_order_event(session: AsyncSession, envelope: WebhookEnvelope) -> None:
    found = await find_submission_order(session, envelope)
    if found is None:
        return
    submission, order = found
    event_type = envelope.event_type
    completed_at = parse_event_time(envelope.data.get("completed_at"))
    if event_type == "pick.confirmed":
        if order.status in {"ordered", "shortage"} and order.picked_at is None:
            order.picked_at = completed_at
    elif event_type == "pack.confirmed":
        if order.status in {"ordered", "shortage"} and order.packed_at is None:
            order.packed_at = completed_at
    elif event_type == "backorder.opened":
        if order.status == "ordered":
            order.status = "shortage"
            order.shortage_at = parse_event_time(envelope.data.get("opened_at"))
    elif event_type == "backorder.fulfillable":
        if order.status == "shortage":
            order.status = "ordered"
            order.shortage_at = None
    elif event_type == "ship.confirmed":
        if order.status in {"ordered", "shortage"}:
            order.status = "shipped"
            order.shipped_at = completed_at
            tracking = envelope.data.get("tracking_numbers") or []
            for index, package in enumerate(envelope.data.get("packages") or []):
                session.add(
                    ShipmentPackage(
                        submission_order_id=order.id,
                        package_external_id=str(package["package_external_id"]),
                        carrier=envelope.data.get("carrier"),
                        service_level=envelope.data.get("service_level"),
                        tracking_number=tracking[index] if index < len(tracking) else None,
                        payload=json.dumps(package, ensure_ascii=False),
                    )
                )
            maybe_complete_submission(submission)


async def process_inventory_event(session: AsyncSession, envelope: WebhookEnvelope) -> None:
    data = envelope.data
    warehouse_id = envelope.warehouse_id or data.get("warehouse_id")
    if not warehouse_id:
        return
    if envelope.event_type == "inventoryadjusted.completed":
        try:
            sku_external_id = UUID(str(data["item_external_id"]))
            bin_external_id = UUID(str(data["bin_external_id"]))
        except (KeyError, ValueError):
            return
        sku = await session.scalar(select(Sku).where(Sku.external_id == sku_external_id))
        if sku is None:
            return
        reason = str(data.get("reason_code", "adjustment")).lower()
        source_type = "cycle_count" if "cycle" in reason else "transfer" if "transfer" in reason else "submission"
        await append_ledger(
            session,
            sku=sku,
            bin_external_id=bin_external_id,
            bin_id=data.get("bin_id"),
            warehouse_id=int(warehouse_id),
            delta=int(data["quantity_delta"]),
            source_type=source_type,
            source_id=int(envelope.event_id),
            operator=data.get("applied_by_user_external_id"),
        )
    elif envelope.event_type == "return.received":
        try:
            bin_external_id = UUID(str(data["bin_external_id"])) if data.get("bin_external_id") else None
        except ValueError:
            bin_external_id = None
        for line in data.get("lines") or []:
            try:
                sku_external_id = UUID(str(line["item_external_id"]))
            except (KeyError, ValueError):
                continue
            sku = await session.scalar(select(Sku).where(Sku.external_id == sku_external_id))
            if sku is None:
                continue
            await append_ledger(
                session,
                sku=sku,
                bin_external_id=bin_external_id,
                bin_id=data.get("bin_id"),
                warehouse_id=int(warehouse_id),
                delta=int(line["quantity_received"]),
                source_type="rma_receive",
                source_id=int(envelope.event_id),
                operator=data.get("received_by_user_external_id"),
            )


@router.post("/sentry")
async def sentry_webhook(
    request: Request,
    x_sentry_timestamp: str | None = Header(default=None, alias="X-Sentry-Timestamp"),
    x_sentry_signature: str | None = Header(default=None, alias="X-Sentry-Signature"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    try:
        timestamp = int(x_sentry_timestamp or "")
    except ValueError:
        raise HTTPException(status_code=401, detail="Webhook 时间戳无效")
    if abs(int(time.time()) - timestamp) > settings.webhook_tolerance_seconds:
        raise HTTPException(status_code=401, detail="Webhook 已超出重放保护窗口")
    if not x_sentry_signature or not verify_hmac(
        raw_body, timestamp, x_sentry_signature, settings.webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Webhook 签名无效")
    try:
        envelope = WebhookEnvelope.model_validate_json(raw_body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Webhook 信封无效: {exc}")
    event_id = str(envelope.event_id)
    if await session.scalar(select(WebhookDedup).where(WebhookDedup.event_id == event_id)):
        return {"accepted": True, "replayed": True}
    if envelope.event_type in {
        "pick.confirmed",
        "pack.confirmed",
        "ship.confirmed",
        "backorder.opened",
        "backorder.fulfillable",
    }:
        await process_order_event(session, envelope)
    elif envelope.event_type in {"inventoryadjusted.completed", "return.received"}:
        await process_inventory_event(session, envelope)
    session.add(
        WebhookDedup(
            event_id=event_id,
            event_type=envelope.event_type,
            payload=raw_body.decode("utf-8"),
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return {"accepted": True, "replayed": True}
    return {
        "accepted": True,
        "replayed": False,
        "handled": envelope.event_type in SUPPORTED_WEBHOOK_EVENTS,
    }
