from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


class CategoryCreate(StrictModel):
    category_name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None
    code_prefix: str | None = Field(
        default=None, min_length=4, max_length=16, pattern="^[A-Z][0-9]{3,15}$"
    )


class CategoryUpdate(StrictModel):
    category_name: str | None = Field(default=None, min_length=1, max_length=128)
    code_prefix: str | None = Field(
        default=None, min_length=4, max_length=16, pattern="^[A-Z][0-9]{3,15}$"
    )
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_name: str
    parent_id: int | None
    code_prefix: str | None
    seq_counter: int
    is_active: bool


class CategoryTreeResponse(CategoryResponse):
    children: list["CategoryTreeResponse"] = Field(default_factory=list)


class SkuCreate(StrictModel):
    category_id: int
    item_name: str = Field(min_length=1, max_length=255)
    code_status: str = Field(default="active", pattern="^(draft|active)$")
    spec_name: str | None = Field(default=None, max_length=255)
    barcode: str | None = Field(default=None, max_length=128)
    weight: Decimal | None = Field(default=None, ge=0)
    length: Decimal | None = Field(default=None, ge=0)
    width: Decimal | None = Field(default=None, ge=0)
    height: Decimal | None = Field(default=None, ge=0)


class SkuUpdate(StrictModel):
    item_name: str | None = Field(default=None, min_length=1, max_length=255)
    spec_name: str | None = Field(default=None, max_length=255)
    barcode: str | None = Field(default=None, max_length=128)
    weight: Decimal | None = Field(default=None, ge=0)
    length: Decimal | None = Field(default=None, ge=0)
    width: Decimal | None = Field(default=None, ge=0)
    height: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class SkuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: UUID
    sku_code: str
    category_id: int
    item_name: str
    code_status: str
    spec_name: str | None
    barcode: str | None
    weight: Decimal | None
    length: Decimal | None
    width: Decimal | None
    height: Decimal | None
    is_active: bool
    promoted_at: datetime | None


class SubmissionLineCreate(StrictModel):
    item_id: int | None = None
    item_desc: str | None = Field(default=None, max_length=255)
    is_new_item: bool = False
    category_id: int | None = None

    @model_validator(mode="after")
    def validate_item_choice(self):
        if self.is_new_item:
            if self.category_id is None or self.item_id is not None:
                raise ValueError("新品行必须填写 category_id 且不能填写 item_id")
        elif self.item_id is None or self.category_id is not None:
            raise ValueError("老品行必须填写 item_id 且不能填写 category_id")
        return self


class SubmissionOrderCreate(StrictModel):
    order_no: str = Field(min_length=1, max_length=128)
    lines: list[SubmissionLineCreate] = Field(min_length=1)


class SubmissionCreate(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    remark: str | None = None
    orders: list[SubmissionOrderCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_order_numbers(self):
        values = [order.order_no for order in self.orders]
        if len(values) != len(set(values)):
            raise ValueError("同一批次内订单号不可重复")
        return self


class RejectOrderRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=2000)


class QuantityItem(StrictModel):
    line_id: int
    qty: int = Field(ge=1)


class QuantityConfirmRequest(StrictModel):
    quantities: list[QuantityItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_lines(self):
        values = [item.line_id for item in self.quantities]
        if len(values) != len(set(values)):
            raise ValueError("line_id 不可重复")
        return self


class CancelRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=2000)


class NewItemName(StrictModel):
    line_id: int
    item_name: str = Field(min_length=1, max_length=255)


class VerifySubmissionRequest(StrictModel):
    new_items: list[NewItemName] = []


class ChangeLineItemRequest(StrictModel):
    item_id: int


class MergeDuplicateRequest(StrictModel):
    existing_item_id: int


class WarehouseCancelOrderRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=2000)


class WebhookEnvelope(StrictModel):
    event_id: int | str
    event_type: str
    event_version: int
    event_timestamp: datetime
    aggregate_type: str
    aggregate_id: str
    warehouse_id: int | None = None
    source_txn_id: str | None = None
    data: dict[str, Any]
