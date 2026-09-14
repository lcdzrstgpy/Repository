"""Hub ERP item projection tests.

Added for Hub ERP integration, 2026-09-14.
"""

import os
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql://sentry:sentry@localhost:5432/sentry")
os.environ.setdefault("JWT_SECRET", "NEVER_USE_THIS_IN_PRODUCTION_32!")

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
sys.path.insert(0, str(API_DIR))

from schemas.items import CreateItemRequest, UpdateItemRequest
from services.inbound_service import _prefetch_line_lookups
from services.mapping_loader import MappingDocument


def test_item_schema_accepts_hub_master_fields():
    item = CreateItemRequest(
        sku="A001-1",
        item_name="Glass cup",
        category_id=101,
        code_status="draft",
        spec_name="350 ml",
    )
    assert item.category_id == 101
    assert item.code_status == "draft"
    assert item.spec_name == "350 ml"


def test_item_schema_defaults_existing_style_create_to_active():
    item = CreateItemRequest(sku="A001-2", item_name="Mug")
    assert item.code_status == "active"
    assert item.category_id is None


@pytest.mark.parametrize("status", ["pending", "disabled", "ACTIVE", ""])
def test_item_schema_rejects_unknown_code_status(status):
    with pytest.raises(ValidationError):
        UpdateItemRequest(code_status=status)


def test_hub_mapping_template_is_valid_and_maps_sales_order_lines():
    mapping_path = ROOT / "db" / "mappings" / "hub.yaml.template"
    document = MappingDocument.model_validate(yaml.safe_load(mapping_path.read_text()))

    assert document.source_system == "hub"
    assert "items" in document.resources
    sales_orders = document.resources["sales_orders"]
    assert sales_orders.line_items is not None
    assert {field.canonical for field in sales_orders.line_items.fields} == {
        "item_id",
        "quantity_ordered",
        "line_number",
    }


def test_sales_order_item_lookup_requires_active_item():
    mapping_path = ROOT / "db" / "mappings" / "hub.yaml.template"
    document = MappingDocument.model_validate(yaml.safe_load(mapping_path.read_text()))

    class Result:
        def fetchall(self):
            return []

    class RecordingDb:
        statement = ""

        def execute(self, statement, params):
            self.statement = str(statement)
            return Result()

    db = RecordingDb()
    _prefetch_line_lookups(
        db,
        document,
        "sales_orders",
        {"lines": [{"line_no": 1, "sku_code": "A001-1", "qty": 2}]},
    )

    assert "i.code_status = 'active'" in db.statement
    assert "i.is_active = TRUE" in db.statement


def test_item_migration_uses_safe_cross_schema_mapping():
    migration = (
        ROOT / "db" / "migrations" / "082_hub_item_master_fields.sql"
    ).read_text()

    assert "ADD COLUMN IF NOT EXISTS category_id BIGINT" in migration
    assert "ADD COLUMN IF NOT EXISTS code_status VARCHAR(16)" in migration
    assert "ADD COLUMN IF NOT EXISTS spec_name VARCHAR(255)" in migration
    assert "to_regclass('hub.category')" in migration
    assert "parent_id IS NOT NULL AND is_active = TRUE" in migration
    assert "ERRCODE = '23503'" in migration
