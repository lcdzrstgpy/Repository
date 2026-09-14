from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import yaml

from app.adapters import SentryWMSAdapter
from app.config import Settings
from app.models import Sku, Submission, SubmissionLine, SubmissionOrder

MAPPING_PATH = (
    Path(__file__).resolve().parents[2] / "wms" / "db" / "mappings" / "hub.yaml.template"
)


def mapping() -> dict:
    return yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8"))


def resolve(payload: dict, path: str):
    node = payload
    for part in path.lstrip("$").lstrip(".").split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def assert_required_fields(spec: dict, payload: dict, label: str) -> None:
    for field in spec.get("fields", []):
        if not field.get("required"):
            continue
        value = resolve(payload, field["source_path"])
        assert value is not None, (
            f"{label} 缺少映射文档声明的必需字段 "
            f"{field['canonical']} ({field['source_path']})"
        )


def assert_line_fields(spec: dict, payload: dict, label: str) -> list[dict]:
    line_spec = spec.get("line_items")
    if not line_spec:
        return []
    lines = resolve(payload, line_spec["source_path"]) or []
    assert isinstance(lines, list) and lines, f"{label} 的 line_items 不能为空"
    for line in lines:
        for field in line_spec.get("fields", []):
            if not field.get("required"):
                continue
            value = resolve(line, field["source_path"])
            assert value is not None, (
                f"{label} 行缺少必需字段 {field['canonical']} ({field['source_path']})"
            )
    return lines


class Capture:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def adapter(self) -> SentryWMSAdapter:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(
                {"url": str(request.url), "body": json.loads(request.content)}
            )
            return httpx.Response(201, json={"canonical_id": str(uuid4())})

        settings = Settings(
            sentry_base_url="http://wms.test/api/v1",
            sentry_token="test-sentry-token-123456",
        )
        return SentryWMSAdapter(settings, transport=httpx.MockTransport(handler))


def make_sku() -> Sku:
    now = datetime.now(timezone.utc)
    return Sku(
        external_id=uuid4(),
        sku_code="A001-1",
        category_id=7,
        item_name="玻璃杯",
        code_status="active",
        spec_name=None,
        barcode=None,
        is_active=True,
        created_at=now,
        promoted_at=now,
    )


def make_order() -> tuple[Submission, SubmissionOrder, Sku]:
    sku = make_sku()
    submission = Submission(
        submission_no="SUB-1",
        idempotency_key="k1",
        remark="整批备注",
        submitted_by="ops",
    )
    order = SubmissionOrder(
        submission_id=1,
        order_no="ORDER-1",
        external_id=uuid4(),
        status="pending",
        confirm_status="confirmed",
    )
    order.lines = [SubmissionLine(line_no=1, qty=2, item=sku)]
    return submission, order, sku


async def test_push_item_payload_matches_inbound_mapping():
    capture = Capture()
    await capture.adapter().push_item(make_sku())

    call = capture.calls[0]
    body = call["body"]
    spec = mapping()["resources"]["items"]
    assert call["url"].endswith("/inbound/items")
    assert_required_fields(spec, body["source_payload"], "items")
    # 订单行以 sku_code 做 cross_system_lookup，而 cross_system_mappings.source_id
    # 取的是信封 external_id，因此 items 的信封 external_id 必须就是 sku_code。
    assert body["external_id"] == "A001-1"
    assert body["source_payload"]["category_id"] == 7
    assert body["source_payload"]["code_status"] == "active"


async def test_create_sales_order_payload_matches_inbound_mapping():
    capture = Capture()
    submission, order, sku = make_order()
    await capture.adapter().create_sales_order(submission, order)

    call = capture.calls[0]
    body = call["body"]
    spec = mapping()["resources"]["sales_orders"]
    assert call["url"].endswith("/inbound/sales_orders")
    assert_required_fields(spec, body["source_payload"], "sales_orders")
    lines = assert_line_fields(spec, body["source_payload"], "sales_orders")
    assert body["external_id"] == str(order.external_id)
    assert lines[0]["sku_code"] == sku.sku_code
    assert lines[0]["qty"] == 2


async def test_cancel_sales_order_uses_status_allowed_by_mapping():
    capture = Capture()
    _, order, _ = make_order()
    await capture.adapter().cancel_sales_order(order, "运营放弃")

    body = capture.calls[0]["body"]
    spec = mapping()["resources"]["sales_orders"]
    status_field = next(f for f in spec["fields"] if f["canonical"] == "status")
    assert body["source_payload"]["status"] == "CANCELLED"
    assert "CANCELLED" in status_field["enum_values"]
    assert_required_fields(spec, body["source_payload"], "sales_orders")
