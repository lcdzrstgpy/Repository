from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends

from app.config import Settings, get_settings
from app.models import Sku, Submission, SubmissionOrder


class SentryAdapterError(RuntimeError):
    pass


class SentryWMSAdapter:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    async def _post(self, resource: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"X-WMS-Token": self.settings.sentry_token}
        async with httpx.AsyncClient(
            base_url=self.settings.sentry_base_url,
            timeout=self.settings.sentry_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(f"/inbound/{resource}", json=body, headers=headers)
        if response.status_code not in (200, 201):
            raise SentryAdapterError(
                f"sentry-wms {resource} 返回 {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    async def push_item(self, sku: Sku) -> dict[str, Any]:
        version = sku.promoted_at or sku.created_at
        return await self._post(
            "items",
            {
                "external_id": sku.sku_code,
                "external_version": version.isoformat(),
                "source_payload": {
                    "sku_code": sku.sku_code,
                    "item_name": sku.item_name,
                    "category_id": sku.category_id,
                    "code_status": sku.code_status,
                    "spec_name": sku.spec_name,
                    "barcode": sku.barcode,
                    "is_active": sku.is_active,
                },
            },
        )

    async def create_sales_order(
        self, submission: Submission, order: SubmissionOrder
    ) -> dict[str, Any]:
        lines: list[dict[str, Any]] = []
        for line in order.lines:
            if line.item is None or line.qty is None:
                raise SentryAdapterError(
                    f"订单 {order.order_no} 第 {line.line_no} 行缺少货号或数量，不能下单"
                )
            lines.append(
                {"line_no": line.line_no, "sku_code": line.item.sku_code, "qty": line.qty}
            )
        version = datetime.now(timezone.utc).isoformat()
        return await self._post(
            "sales_orders",
            {
                "external_id": str(order.external_id),
                "external_version": version,
                "source_payload": {
                    "order_no": order.order_no,
                    "remark": submission.remark,
                    "order_origin": "hub",
                    "status": "OPEN",
                    "lines": lines,
                },
            },
        )

    async def cancel_sales_order(self, order: SubmissionOrder, reason: str) -> dict[str, Any]:
        version = datetime.now(timezone.utc).isoformat()
        return await self._post(
            "sales_orders",
            {
                "external_id": str(order.external_id),
                "external_version": version,
                "source_payload": {
                    "order_no": order.order_no,
                    "status": "CANCELLED",
                },
            },
        )


def get_sentry_adapter(settings: Settings = Depends(get_settings)) -> SentryWMSAdapter:
    return SentryWMSAdapter(settings)
