from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SchemaMigration(Base):
    __tablename__ = "schema_migration"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "user"
    __table_args__ = (CheckConstraint("role = 'ops'", name="ck_user_role_ops"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="ops", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Category(Base, TimestampMixin):
    __tablename__ = "category"
    __table_args__ = (
        CheckConstraint("length(trim(category_name)) > 0", name="ck_category_name_not_blank"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_category_not_self_parent"),
        CheckConstraint(
            "(parent_id IS NULL AND code_prefix IS NULL) OR "
            "(parent_id IS NOT NULL AND code_prefix ~ '^[A-Z][0-9]{3,15}$')",
            name="ck_category_prefix_by_level",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("seq_counter >= 0", name="ck_category_seq_counter"),
        Index(
            "uq_category_root_name",
            "category_name",
            unique=True,
            sqlite_where=text("parent_id IS NULL"),
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_category_sibling_name",
            "parent_id",
            "category_name",
            unique=True,
            sqlite_where=text("parent_id IS NOT NULL"),
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("hub.category.id", ondelete="RESTRICT"), nullable=True
    )
    code_prefix: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    seq_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent: Mapped[Category | None] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    skus: Mapped[list[Sku]] = relationship(back_populates="category")


class Sku(Base):
    __tablename__ = "sku"
    __table_args__ = (
        CheckConstraint("code_status IN ('draft', 'active')", name="ck_sku_code_status"),
        CheckConstraint(
            "sku_code ~ '^[A-Z][A-Z0-9]{1,15}-[1-9][0-9]*$'",
            name="ck_sku_code_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("length(trim(item_name)) > 0", name="ck_sku_item_name_not_blank"),
        CheckConstraint(
            "(weight IS NULL OR weight >= 0) AND "
            "(length IS NULL OR length >= 0) AND "
            "(width IS NULL OR width >= 0) AND "
            "(height IS NULL OR height >= 0)",
            name="ck_sku_dimensions_nonnegative",
        ),
        CheckConstraint(
            "(code_status = 'draft' AND promoted_at IS NULL) OR "
            "(code_status = 'active' AND promoted_at IS NOT NULL)",
            name="ck_sku_promoted_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, unique=True, nullable=False)
    sku_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("hub.category.id", ondelete="RESTRICT"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    code_status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    spec_name: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(128))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    length: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[Category] = relationship(back_populates="skus")


class Submission(Base, TimestampMixin):
    __tablename__ = "submission"
    __table_args__ = (
        CheckConstraint("status BETWEEN 0 AND 6", name="ck_submission_status"),
        CheckConstraint("length(trim(submission_no)) > 0", name="ck_submission_no_not_blank"),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0", name="ck_submission_idempotency_not_blank"
        ),
        CheckConstraint("length(trim(submitted_by)) > 0", name="ck_submission_submitter_not_blank"),
        CheckConstraint(
            "(status <> 6 OR completed_at IS NOT NULL) AND "
            "(status <> 0 OR (cancelled_at IS NOT NULL AND "
            "length(trim(COALESCE(cancel_reason, ''))) > 0))",
            name="ck_submission_terminal_fields",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    alert_1h_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alert_2h_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    orders: Mapped[list[SubmissionOrder]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )


class SubmissionOrder(Base, TimestampMixin):
    __tablename__ = "submission_order"
    __table_args__ = (
        UniqueConstraint("submission_id", "order_no", name="uq_submission_order_no"),
        CheckConstraint(
            "status IN ('pending','ordered','shortage','shipped','cancelled')",
            name="ck_submission_order_status",
        ),
        CheckConstraint(
            "confirm_status IN ('pending','confirmed','rejected')",
            name="ck_submission_order_confirm_status",
        ),
        CheckConstraint(
            "reject_count BETWEEN 0 AND 3", name="ck_submission_order_reject_count"
        ),
        CheckConstraint("length(trim(order_no)) > 0", name="ck_submission_order_no_not_blank"),
        CheckConstraint(
            "status <> 'shortage' OR shortage_at IS NOT NULL",
            name="ck_submission_order_shortage_time",
        ),
        CheckConstraint(
            "status <> 'shipped' OR shipped_at IS NOT NULL",
            name="ck_submission_order_shipped_time",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("hub.submission.id", ondelete="CASCADE"), nullable=False
    )
    order_no: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    confirm_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reject_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sales_order_id: Mapped[int | None] = mapped_column(BigInteger)
    wms_canonical_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    shortage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submission: Mapped[Submission] = relationship(back_populates="orders")
    lines: Mapped[list[SubmissionLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    packages: Mapped[list[ShipmentPackage]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class SubmissionLine(Base, TimestampMixin):
    __tablename__ = "submission_line"
    __table_args__ = (
        UniqueConstraint("submission_order_id", "line_no", name="uq_order_line_no"),
        CheckConstraint("line_no >= 1", name="ck_submission_line_no"),
        CheckConstraint(
            "(is_new_item AND category_id IS NOT NULL) OR "
            "(NOT is_new_item AND category_id IS NULL AND item_id IS NOT NULL)",
            name="ck_submission_line_shape",
        ),
        CheckConstraint("qty IS NULL OR qty >= 1", name="ck_submission_line_qty"),
        CheckConstraint(
            "qty_locked_at IS NULL OR qty IS NOT NULL", name="ck_submission_line_qty_lock"
        ),
        CheckConstraint(
            "line_status IN ('pending','rejected','confirmed')",
            name="ck_submission_line_status",
        ),
        CheckConstraint(
            "line_status <> 'rejected' OR "
            "length(trim(COALESCE(reject_reason, ''))) > 0",
            name="ck_submission_line_reject_reason",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_order_id: Mapped[int] = mapped_column(
        ForeignKey("hub.submission_order.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("hub.sku.id", ondelete="RESTRICT"), nullable=True
    )
    item_desc: Mapped[str | None] = mapped_column(String(255))
    is_new_item: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("hub.category.id", ondelete="RESTRICT"), nullable=True
    )
    draft_sku_code: Mapped[str | None] = mapped_column(String(64))
    qty: Mapped[int | None] = mapped_column(Integer)
    qty_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    line_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(Text)

    order: Mapped[SubmissionOrder] = relationship(back_populates="lines")
    item: Mapped[Sku | None] = relationship(foreign_keys=[item_id], lazy="selectin")
    category: Mapped[Category | None] = relationship(foreign_keys=[category_id], lazy="selectin")
    review_logs: Mapped[list[SkuReviewLog]] = relationship(
        back_populates="line", cascade="all, delete-orphan"
    )


class SkuReviewLog(Base):
    __tablename__ = "sku_review_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('create_draft','promote','merge_duplicate','change_item')",
            name="ck_sku_review_action",
        ),
        CheckConstraint(
            "length(trim(operator)) > 0", name="ck_sku_review_operator_not_blank"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_line_id: Mapped[int] = mapped_column(
        ForeignKey("hub.submission_line.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    from_sku_id: Mapped[int | None] = mapped_column(BigInteger)
    to_sku_id: Mapped[int | None] = mapped_column(BigInteger)
    draft_sku_code: Mapped[str | None] = mapped_column(String(64))
    operator: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    line: Mapped[SubmissionLine] = relationship(back_populates="review_logs")


class InventoryLedger(Base):
    __tablename__ = "inventory_ledger"
    __table_args__ = (
        CheckConstraint("delta <> 0", name="ck_inventory_ledger_delta_nonzero"),
        CheckConstraint(
            "balance_after >= 0", name="ck_inventory_ledger_balance_nonnegative"
        ),
        CheckConstraint(
            "source_type IN ('submission','rma_receive','cycle_count','transfer')",
            name="ck_inventory_ledger_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("hub.sku.id", ondelete="RESTRICT"), nullable=False)
    bin_id: Mapped[int | None] = mapped_column(BigInteger)
    bin_external_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebhookDedup(Base):
    __tablename__ = "webhook_dedup"
    __table_args__ = (
        CheckConstraint("length(trim(event_id)) > 0", name="ck_webhook_event_id_not_blank"),
        CheckConstraint(
            "length(trim(event_type)) > 0", name="ck_webhook_event_type_not_blank"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShipmentPackage(Base):
    __tablename__ = "shipment_package"
    __table_args__ = (
        UniqueConstraint("submission_order_id", "package_external_id", name="uq_order_package"),
        CheckConstraint(
            "length(trim(package_external_id)) > 0", name="ck_package_external_id_not_blank"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_order_id: Mapped[int] = mapped_column(
        ForeignKey("hub.submission_order.id", ondelete="CASCADE"), nullable=False
    )
    package_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    carrier: Mapped[str | None] = mapped_column(String(128))
    service_level: Mapped[str | None] = mapped_column(String(128))
    tracking_number: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[SubmissionOrder] = relationship(back_populates="packages")


class SubmissionAuditLog(Base):
    __tablename__ = "submission_audit_log"
    __table_args__ = (
        CheckConstraint(
            "length(trim(action)) > 0", name="ck_submission_audit_action_not_blank"
        ),
        CheckConstraint(
            "length(trim(operator)) > 0", name="ck_submission_audit_operator_not_blank"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("hub.submission.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
