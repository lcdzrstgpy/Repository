-- Modified for Hub ERP integration, 2026-09-14.
-- 082: link the WMS item projection to hub.category and carry SKU review state.
--
-- hub.category is owned and migrated by the independent Hub service. A static
-- cross-schema FK would make WMS bootstrap order-dependent, so this migration
-- uses a write-time mapping trigger instead: NULL remains valid for legacy
-- items, while every non-NULL category_id must resolve to an active level-two
-- hub category. The Hub must soft-disable referenced categories rather than
-- hard-delete them; see docs/hub-integration.md.

SET lock_timeout = '5s';
SET statement_timeout = '120s';

BEGIN;

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS category_id BIGINT,
    ADD COLUMN IF NOT EXISTS code_status VARCHAR(16) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS spec_name VARCHAR(255);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'items'::regclass
           AND conname = 'ck_items_code_status'
    ) THEN
        ALTER TABLE items
            ADD CONSTRAINT ck_items_code_status
            CHECK (code_status IN ('draft', 'active'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_items_category_id ON items(category_id);
CREATE INDEX IF NOT EXISTS ix_items_code_status ON items(code_status);

CREATE OR REPLACE FUNCTION validate_items_hub_category()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    category_is_valid BOOLEAN;
BEGIN
    IF NEW.category_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF to_regclass('hub.category') IS NULL THEN
        RAISE EXCEPTION
            'hub.category is unavailable; cannot map items.category_id=%',
            NEW.category_id
            USING ERRCODE = '23503';
    END IF;

    EXECUTE
        'SELECT EXISTS ('
        'SELECT 1 FROM hub.category '
        'WHERE id = $1 AND parent_id IS NOT NULL AND is_active = TRUE)'
        INTO category_is_valid
        USING NEW.category_id;

    IF NOT category_is_valid THEN
        RAISE EXCEPTION
            'items.category_id=% must reference an active level-two hub.category',
            NEW.category_id
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_items_validate_hub_category ON items;
CREATE TRIGGER trg_items_validate_hub_category
    BEFORE INSERT OR UPDATE OF category_id ON items
    FOR EACH ROW
    EXECUTE FUNCTION validate_items_hub_category();

COMMENT ON COLUMN items.category_id IS
    'Logical reference to hub.category.id. Enforced on item writes by trg_items_validate_hub_category without owning the Hub schema lifecycle. (mig 082)';
COMMENT ON COLUMN items.code_status IS
    'Hub SKU review state: draft or active. Existing WMS items default to active. (mig 082)';
COMMENT ON COLUMN items.spec_name IS
    'Optional specification description mirrored from the Hub item master. (mig 082)';

COMMIT;
