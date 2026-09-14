from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.models import InventoryLedger, Sku, Submission, WebhookDedup


def submission_payload(api, key="idem-1", order_count=1, new_item=False):
    orders = []
    for index in range(order_count):
        line = (
            {
                "is_new_item": True,
                "category_id": api["leaf_id"],
                "item_desc": "新品杯",
            }
            if new_item
            else {"item_id": api["sku_id"], "item_desc": "玻璃杯"}
        )
        orders.append({"order_no": f"ORDER-{key}-{index + 1}", "lines": [line]})
    return {"idempotency_key": key, "remark": "测试批次", "orders": orders}


async def create_and_verify(api, key="idem-flow", order_count=1):
    client = api["client"]
    created = await client.post(
        "/api/v1/submissions",
        json=submission_payload(api, key, order_count),
        headers=api["ops_headers"],
    )
    assert created.status_code == 201, created.text
    body = created.json()
    verified = await client.post(
        f"/api/v1/warehouse/submissions/{body['id']}/verify",
        json={"new_items": []},
        headers=api["wms_headers"],
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


async def ready_for_dispatch(api, key="idem-ready", order_count=1):
    client = api["client"]
    body = await create_and_verify(api, key, order_count)
    confirmed = await client.post(
        f"/api/v1/submissions/{body['id']}/confirm-items", headers=api["ops_headers"]
    )
    assert confirmed.status_code == 200, confirmed.text
    quantities = [
        {"line_id": line["id"], "qty": 2}
        for order in confirmed.json()["orders"]
        for line in order["lines"]
    ]
    locked = await client.post(
        f"/api/v1/submissions/{body['id']}/confirm-quantities",
        json={"quantities": quantities},
        headers=api["ops_headers"],
    )
    assert locked.status_code == 200, locked.text
    return locked.json()


def signed_event(api, envelope, *, valid=True):
    body = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    timestamp = int(time.time())
    secret = api["settings"].webhook_secret if valid else "wrong-secret"
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode("ascii") + body, hashlib.sha256
    ).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Sentry-Timestamp": str(timestamp),
        "X-Sentry-Signature": f"sha256={digest}",
    }


def envelope(event_id, event_type, external_id, data, warehouse_id=1):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": 1,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate_type": "sales_order",
        "aggregate_id": external_id,
        "warehouse_id": warehouse_id,
        "source_txn_id": str(uuid4()),
        "data": data,
    }


async def post_event(api, event):
    body, headers = signed_event(api, event)
    return await api["client"].post("/api/v1/webhooks/sentry", content=body, headers=headers)


async def test_login_search_submission_idempotency_and_initial_validation(api):
    client = api["client"]
    me = await client.get("/api/v1/auth/me", headers=api["ops_headers"])
    assert me.status_code == 200
    assert me.json()["role"] == "ops"

    search = await client.get(
        "/api/v1/catalog/skus/search?q=玻璃", headers=api["ops_headers"]
    )
    assert search.status_code == 200
    assert search.json()[0]["sku_code"] == "A001-1"

    payload = submission_payload(api, "idem-replay")
    first = await client.post("/api/v1/submissions", json=payload, headers=api["ops_headers"])
    second = await client.post("/api/v1/submissions", json=payload, headers=api["ops_headers"])
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    invalid = submission_payload(api, "idem-invalid")
    invalid["orders"][0]["lines"][0]["item_id"] = 999999
    response = await client.post(
        "/api/v1/submissions", json=invalid, headers=api["ops_headers"]
    )
    assert response.status_code == 422


async def test_order_rejection_limit_quantity_lock_and_ops_cancel_boundary(api):
    client = api["client"]
    body = await create_and_verify(api, "idem-reject")
    submission_id = body["id"]
    order_id = body["orders"][0]["id"]

    for attempt in range(3):
        rejected = await client.post(
            f"/api/v1/submissions/{submission_id}/orders/{order_id}/reject",
            json={"reason": f"第 {attempt + 1} 次驳回"},
            headers=api["ops_headers"],
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == 1
        assert rejected.json()["orders"][0]["reject_count"] == attempt + 1
        reworked = await client.post(
            f"/api/v1/warehouse/submissions/{submission_id}/rework",
            headers=api["wms_headers"],
        )
        assert reworked.status_code == 200, reworked.text

    fourth = await client.post(
        f"/api/v1/submissions/{submission_id}/orders/{order_id}/reject",
        json={"reason": "超过上限"},
        headers=api["ops_headers"],
    )
    assert fourth.status_code == 409

    confirmed = await client.post(
        f"/api/v1/submissions/{submission_id}/confirm-items", headers=api["ops_headers"]
    )
    line_id = confirmed.json()["orders"][0]["lines"][0]["id"]
    locked = await client.post(
        f"/api/v1/submissions/{submission_id}/confirm-quantities",
        json={"quantities": [{"line_id": line_id, "qty": 3}]},
        headers=api["ops_headers"],
    )
    assert locked.status_code == 200
    assert locked.json()["status"] == 4

    relock = await client.post(
        f"/api/v1/submissions/{submission_id}/confirm-quantities",
        json={"quantities": [{"line_id": line_id, "qty": 4}]},
        headers=api["ops_headers"],
    )
    assert relock.status_code == 409
    cancel = await client.post(
        f"/api/v1/submissions/{submission_id}/cancel",
        json={"reason": "运营尝试取消"},
        headers=api["ops_headers"],
    )
    assert cancel.status_code == 409


async def test_new_sku_must_be_promoted_and_number_is_not_reused(api):
    client = api["client"]
    created = await client.post(
        "/api/v1/submissions",
        json=submission_payload(api, "idem-new", new_item=True),
        headers=api["ops_headers"],
    )
    body = created.json()
    line_id = body["orders"][0]["lines"][0]["id"]
    verified = await client.post(
        f"/api/v1/warehouse/submissions/{body['id']}/verify",
        json={"new_items": [{"line_id": line_id, "item_name": "马克杯"}]},
        headers=api["wms_headers"],
    )
    assert verified.status_code == 200
    draft = verified.json()["orders"][0]["lines"][0]
    assert draft["draft_sku_code"] == "A001-2"

    blocked = await client.post(
        f"/api/v1/submissions/{body['id']}/confirm-items", headers=api["ops_headers"]
    )
    assert blocked.status_code == 409

    promoted = await client.post(
        f"/api/v1/warehouse/skus/{draft['item_id']}/promote", headers=api["wms_headers"]
    )
    assert promoted.status_code == 200
    assert draft["item_id"] in api["adapter"].items
    confirmed = await client.post(
        f"/api/v1/submissions/{body['id']}/confirm-items", headers=api["ops_headers"]
    )
    assert confirmed.status_code == 200

    duplicate_batch = await client.post(
        "/api/v1/submissions",
        json=submission_payload(api, "idem-duplicate", new_item=True),
        headers=api["ops_headers"],
    )
    duplicate_line_id = duplicate_batch.json()["orders"][0]["lines"][0]["id"]
    duplicate_verified = await client.post(
        f"/api/v1/warehouse/submissions/{duplicate_batch.json()['id']}/verify",
        json={"new_items": [{"line_id": duplicate_line_id, "item_name": "重复玻璃杯"}]},
        headers=api["wms_headers"],
    )
    duplicate_code = duplicate_verified.json()["orders"][0]["lines"][0]["draft_sku_code"]
    assert duplicate_code == "A001-3"
    merged = await client.post(
        f"/api/v1/warehouse/submissions/{duplicate_batch.json()['id']}/lines/{duplicate_line_id}/merge-duplicate",
        json={"existing_item_id": api["sku_id"]},
        headers=api["wms_headers"],
    )
    assert merged.status_code == 200, merged.text
    async with api["session_factory"]() as session:
        assert await session.scalar(select(Sku).where(Sku.sku_code == duplicate_code)) is None

    created_sku = await client.post(
        "/api/v1/warehouse/catalog/skus",
        json={"category_id": api["leaf_id"], "item_name": "新水杯", "code_status": "active"},
        headers=api["wms_headers"],
    )
    assert created_sku.status_code == 201, created_sku.text
    assert created_sku.json()["sku_code"] == "A001-4"


async def test_per_order_shortage_webhook_dedup_and_batch_completion(api):
    client = api["client"]
    ready = await ready_for_dispatch(api, "idem-webhook", order_count=2)
    submission_id = ready["id"]
    dispatched = await client.post(
        f"/api/v1/warehouse/submissions/{submission_id}/dispatch",
        headers=api["wms_headers"],
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == 5
    first, second = dispatched.json()["orders"]

    shortage_event = envelope(
        101,
        "backorder.opened",
        first["external_id"],
        {
            "backorder_so_external_id": first["external_id"],
            "opened_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    shortage = await post_event(api, shortage_event)
    replay = await post_event(api, shortage_event)
    assert shortage.status_code == 200
    assert replay.json()["replayed"] is True

    ship_second = envelope(
        102,
        "ship.confirmed",
        second["external_id"],
        {
            "sales_order_external_id": second["external_id"],
            "tracking_numbers": ["TRACK-2"],
            "carrier": "manual",
            "service_level": None,
            "packages": [{"package_external_id": "PKG-2", "lines": []}],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert (await post_event(api, ship_second)).status_code == 200
    detail = await client.get(
        f"/api/v1/submissions/{submission_id}", headers=api["ops_headers"]
    )
    assert detail.json()["status"] == 5
    statuses = {item["id"]: item["status"] for item in detail.json()["orders"]}
    assert statuses[first["id"]] == "shortage"
    assert statuses[second["id"]] == "shipped"

    fulfillable = envelope(
        103,
        "backorder.fulfillable",
        first["external_id"],
        {"backorder_so_external_id": first["external_id"]},
    )
    await post_event(api, fulfillable)
    ship_first = envelope(
        104,
        "ship.confirmed",
        first["external_id"],
        {
            "sales_order_external_id": first["external_id"],
            "tracking_numbers": [],
            "carrier": "pickup",
            "service_level": None,
            "packages": [{"package_external_id": "PKG-1", "lines": []}],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    await post_event(api, ship_first)
    completed = await client.get(
        f"/api/v1/submissions/{submission_id}", headers=api["ops_headers"]
    )
    assert completed.json()["status"] == 6

    async with api["session_factory"]() as session:
        assert await session.scalar(select(func.count(WebhookDedup.id))) == 4


async def test_webhook_hmac_and_inventory_ledger(api):
    event = envelope(
        201,
        "inventoryadjusted.completed",
        str(uuid4()),
        {
            "adjustment_external_id": str(uuid4()),
            "item_external_id": api["sku_external_id"],
            "bin_external_id": str(uuid4()),
            "quantity_delta": 7,
            "reason_code": "cycle_count",
            "applied_by_user_external_id": None,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    body, bad_headers = signed_event(api, event, valid=False)
    bad = await api["client"].post(
        "/api/v1/webhooks/sentry", content=body, headers=bad_headers
    )
    assert bad.status_code == 401

    good = await post_event(api, event)
    assert good.status_code == 200, good.text
    async with api["session_factory"]() as session:
        row = await session.scalar(select(InventoryLedger))
        assert row.delta == 7
        assert row.balance_after == 7
        assert row.source_type == "cycle_count"


async def test_timeout_scan_alerts_responsible_party_then_both(api):
    created = await api["client"].post(
        "/api/v1/submissions",
        json=submission_payload(api, "idem-timeout"),
        headers=api["ops_headers"],
    )
    assert created.status_code == 201, created.text
    submission_id = created.json()["id"]

    async def age(entered_at):
        async with api["session_factory"]() as session:
            submission = await session.get(Submission, submission_id)
            submission.status_entered_at = entered_at
            await session.commit()

    # 批次 ① 的责任方是仓库侧，1h 只提醒仓库
    await age(datetime.now(timezone.utc) - timedelta(hours=1, minutes=30))
    first = await api["client"].post(
        "/api/v1/system/timeouts/scan", headers=api["wms_headers"]
    )
    assert first.status_code == 200, first.text
    alerts = first.json()["alerts"]
    assert [alert["level"] for alert in alerts] == [1]
    assert alerts[0]["recipients"] == ["warehouse"]

    # 1h 已发过且未到 2h，不重复提醒
    repeat = await api["client"].post(
        "/api/v1/system/timeouts/scan", headers=api["wms_headers"]
    )
    assert repeat.json()["alerts"] == []

    # 超过 2h 后两侧同时提醒，且不再重复
    await age(datetime.now(timezone.utc) - timedelta(hours=2, minutes=30))
    second = await api["client"].post(
        "/api/v1/system/timeouts/scan", headers=api["wms_headers"]
    )
    alerts = second.json()["alerts"]
    assert [alert["level"] for alert in alerts] == [2]
    assert alerts[0]["recipients"] == ["ops", "warehouse"]

    third = await api["client"].post(
        "/api/v1/system/timeouts/scan", headers=api["wms_headers"]
    )
    assert third.json()["alerts"] == []
