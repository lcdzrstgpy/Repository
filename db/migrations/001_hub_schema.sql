\set ON_ERROR_STOP on

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS hub;

CREATE TABLE IF NOT EXISTS hub.schema_migration (
    version VARCHAR(64) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS hub."user" (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'ops',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_user_role_ops CHECK (role = 'ops')
);

CREATE TABLE IF NOT EXISTS hub.category (
    id BIGSERIAL PRIMARY KEY,
    category_name VARCHAR(128) NOT NULL,
    parent_id BIGINT REFERENCES hub.category(id) ON DELETE RESTRICT,
    code_prefix VARCHAR(16) UNIQUE,
    seq_counter INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_category_name_not_blank CHECK (btrim(category_name) <> ''),
    CONSTRAINT ck_category_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id),
    CONSTRAINT ck_category_prefix_by_level CHECK (
        (parent_id IS NULL AND code_prefix IS NULL)
        OR (parent_id IS NOT NULL AND code_prefix ~ '^[A-Z][0-9]{3,15}$')
    ),
    CONSTRAINT ck_category_seq_counter CHECK (seq_counter >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_category_root_name
    ON hub.category (category_name) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_sibling_name
    ON hub.category (parent_id, category_name) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_category_parent_active
    ON hub.category (parent_id, is_active);

CREATE TABLE IF NOT EXISTS hub.sku (
    id BIGSERIAL PRIMARY KEY,
    external_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    sku_code VARCHAR(64) NOT NULL UNIQUE,
    category_id BIGINT NOT NULL REFERENCES hub.category(id) ON DELETE RESTRICT,
    item_name VARCHAR(255) NOT NULL,
    code_status VARCHAR(16) NOT NULL DEFAULT 'draft',
    spec_name VARCHAR(255),
    barcode VARCHAR(128),
    weight NUMERIC(12, 3),
    length NUMERIC(12, 3),
    width NUMERIC(12, 3),
    height NUMERIC(12, 3),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    promoted_at TIMESTAMPTZ,
    CONSTRAINT ck_sku_code_status CHECK (code_status IN ('draft', 'active')),
    CONSTRAINT ck_sku_code_format CHECK (sku_code ~ '^[A-Z][A-Z0-9]{1,15}-[1-9][0-9]*$'),
    CONSTRAINT ck_sku_item_name_not_blank CHECK (btrim(item_name) <> ''),
    CONSTRAINT ck_sku_dimensions_nonnegative CHECK (
        (weight IS NULL OR weight >= 0)
        AND (length IS NULL OR length >= 0)
        AND (width IS NULL OR width >= 0)
        AND (height IS NULL OR height >= 0)
    ),
    CONSTRAINT ck_sku_promoted_at CHECK (
        (code_status = 'draft' AND promoted_at IS NULL)
        OR (code_status = 'active' AND promoted_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_sku_category ON hub.sku (category_id);
CREATE INDEX IF NOT EXISTS ix_sku_status_active ON hub.sku (code_status, is_active);
CREATE INDEX IF NOT EXISTS ix_sku_item_name_trgm ON hub.sku USING gin (item_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_sku_code_trgm ON hub.sku USING gin (sku_code gin_trgm_ops);

CREATE TABLE IF NOT EXISTS hub.submission (
    id BIGSERIAL PRIMARY KEY,
    submission_no VARCHAR(64) NOT NULL UNIQUE,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    status SMALLINT NOT NULL DEFAULT 1,
    remark TEXT,
    submitted_by VARCHAR(128) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    status_entered_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    alert_1h_at TIMESTAMPTZ,
    alert_2h_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancel_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_submission_status CHECK (status BETWEEN 0 AND 6),
    CONSTRAINT ck_submission_no_not_blank CHECK (btrim(submission_no) <> ''),
    CONSTRAINT ck_submission_idempotency_not_blank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_submission_submitter_not_blank CHECK (btrim(submitted_by) <> ''),
    CONSTRAINT ck_submission_terminal_fields CHECK (
        (status <> 6 OR completed_at IS NOT NULL)
        AND (status <> 0 OR (cancelled_at IS NOT NULL AND btrim(COALESCE(cancel_reason, '')) <> ''))
    )
);

CREATE INDEX IF NOT EXISTS ix_submission_status_entered
    ON hub.submission (status, status_entered_at) WHERE status BETWEEN 1 AND 4;
CREATE INDEX IF NOT EXISTS ix_submission_submitter_time
    ON hub.submission (submitted_by, submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_submission_submitted_at
    ON hub.submission (submitted_at DESC);

CREATE TABLE IF NOT EXISTS hub.submission_order (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES hub.submission(id) ON DELETE CASCADE,
    order_no VARCHAR(128) NOT NULL,
    external_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    confirm_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    reject_count INTEGER NOT NULL DEFAULT 0,
    sales_order_id BIGINT,
    wms_canonical_id UUID,
    shortage_at TIMESTAMPTZ,
    picked_at TIMESTAMPTZ,
    packed_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_submission_order_no UNIQUE (submission_id, order_no),
    CONSTRAINT ck_submission_order_no_not_blank CHECK (btrim(order_no) <> ''),
    CONSTRAINT ck_submission_order_status CHECK (
        status IN ('pending', 'ordered', 'shortage', 'shipped', 'cancelled')
    ),
    CONSTRAINT ck_submission_order_confirm_status CHECK (
        confirm_status IN ('pending', 'confirmed', 'rejected')
    ),
    CONSTRAINT ck_submission_order_reject_count CHECK (reject_count BETWEEN 0 AND 3),
    CONSTRAINT ck_submission_order_shortage_time CHECK (
        status <> 'shortage' OR shortage_at IS NOT NULL
    ),
    CONSTRAINT ck_submission_order_shipped_time CHECK (
        status <> 'shipped' OR shipped_at IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS ix_submission_order_submission ON hub.submission_order (submission_id);
CREATE INDEX IF NOT EXISTS ix_submission_order_order_no_trgm
    ON hub.submission_order USING gin (order_no gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_submission_order_status ON hub.submission_order (status);
CREATE INDEX IF NOT EXISTS ix_submission_order_confirm_status
    ON hub.submission_order (confirm_status) WHERE confirm_status <> 'confirmed';
CREATE INDEX IF NOT EXISTS ix_submission_order_sales_order_id
    ON hub.submission_order (sales_order_id) WHERE sales_order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS hub.submission_line (
    id BIGSERIAL PRIMARY KEY,
    submission_order_id BIGINT NOT NULL REFERENCES hub.submission_order(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    item_id BIGINT REFERENCES hub.sku(id) ON DELETE RESTRICT,
    item_desc VARCHAR(255),
    is_new_item BOOLEAN NOT NULL DEFAULT FALSE,
    category_id BIGINT REFERENCES hub.category(id) ON DELETE RESTRICT,
    draft_sku_code VARCHAR(64),
    qty INTEGER,
    qty_locked_at TIMESTAMPTZ,
    line_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    reject_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_order_line_no UNIQUE (submission_order_id, line_no),
    CONSTRAINT ck_submission_line_no CHECK (line_no >= 1),
    CONSTRAINT ck_submission_line_shape CHECK (
        (is_new_item AND category_id IS NOT NULL)
        OR (NOT is_new_item AND category_id IS NULL AND item_id IS NOT NULL)
    ),
    CONSTRAINT ck_submission_line_qty CHECK (qty IS NULL OR qty >= 1),
    CONSTRAINT ck_submission_line_qty_lock CHECK (qty_locked_at IS NULL OR qty IS NOT NULL),
    CONSTRAINT ck_submission_line_status CHECK (
        line_status IN ('pending', 'rejected', 'confirmed')
    ),
    CONSTRAINT ck_submission_line_reject_reason CHECK (
        line_status <> 'rejected' OR btrim(COALESCE(reject_reason, '')) <> ''
    )
);

CREATE INDEX IF NOT EXISTS ix_submission_line_order ON hub.submission_line (submission_order_id);
CREATE INDEX IF NOT EXISTS ix_submission_line_item ON hub.submission_line (item_id) WHERE item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_submission_line_category
    ON hub.submission_line (category_id) WHERE category_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS hub.sku_review_log (
    id BIGSERIAL PRIMARY KEY,
    submission_line_id BIGINT NOT NULL REFERENCES hub.submission_line(id) ON DELETE CASCADE,
    action VARCHAR(24) NOT NULL,
    from_sku_id BIGINT,
    to_sku_id BIGINT,
    draft_sku_code VARCHAR(64),
    operator VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_sku_review_action CHECK (
        action IN ('create_draft', 'promote', 'merge_duplicate', 'change_item')
    ),
    CONSTRAINT ck_sku_review_operator_not_blank CHECK (btrim(operator) <> '')
);

CREATE INDEX IF NOT EXISTS ix_sku_review_line_time
    ON hub.sku_review_log (submission_line_id, created_at DESC);

CREATE TABLE IF NOT EXISTS hub.inventory_ledger (
    id BIGSERIAL PRIMARY KEY,
    sku_id BIGINT NOT NULL REFERENCES hub.sku(id) ON DELETE RESTRICT,
    bin_id BIGINT,
    bin_external_id UUID,
    warehouse_id BIGINT NOT NULL,
    delta INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id BIGINT NOT NULL,
    operator VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_inventory_ledger_delta_nonzero CHECK (delta <> 0),
    CONSTRAINT ck_inventory_ledger_balance_nonnegative CHECK (balance_after >= 0),
    CONSTRAINT ck_inventory_ledger_source_type CHECK (
        source_type IN ('submission', 'rma_receive', 'cycle_count', 'transfer')
    )
);

CREATE INDEX IF NOT EXISTS ix_inventory_ledger_sku_time
    ON hub.inventory_ledger (sku_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_inventory_ledger_bin_time
    ON hub.inventory_ledger (warehouse_id, bin_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_inventory_ledger_bin_external_time
    ON hub.inventory_ledger (bin_external_id, created_at DESC) WHERE bin_external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_inventory_ledger_source
    ON hub.inventory_ledger (source_type, source_id);

CREATE TABLE IF NOT EXISTS hub.webhook_dedup (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(128) NOT NULL UNIQUE,
    event_type VARCHAR(64) NOT NULL,
    payload TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_webhook_event_id_not_blank CHECK (btrim(event_id) <> ''),
    CONSTRAINT ck_webhook_event_type_not_blank CHECK (btrim(event_type) <> '')
);

CREATE INDEX IF NOT EXISTS ix_webhook_dedup_processed_at
    ON hub.webhook_dedup (processed_at DESC);

CREATE TABLE IF NOT EXISTS hub.shipment_package (
    id BIGSERIAL PRIMARY KEY,
    submission_order_id BIGINT NOT NULL REFERENCES hub.submission_order(id) ON DELETE CASCADE,
    package_external_id VARCHAR(128) NOT NULL,
    carrier VARCHAR(128),
    service_level VARCHAR(128),
    tracking_number VARCHAR(255),
    payload TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_order_package UNIQUE (submission_order_id, package_external_id),
    CONSTRAINT ck_package_external_id_not_blank CHECK (btrim(package_external_id) <> '')
);

CREATE INDEX IF NOT EXISTS ix_shipment_package_order
    ON hub.shipment_package (submission_order_id, created_at);
CREATE INDEX IF NOT EXISTS ix_shipment_package_tracking
    ON hub.shipment_package (tracking_number) WHERE tracking_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS hub.submission_audit_log (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES hub.submission(id) ON DELETE CASCADE,
    action VARCHAR(64) NOT NULL,
    operator VARCHAR(128) NOT NULL,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_submission_audit_action_not_blank CHECK (btrim(action) <> ''),
    CONSTRAINT ck_submission_audit_operator_not_blank CHECK (btrim(operator) <> '')
);

CREATE INDEX IF NOT EXISTS ix_submission_audit_submission_time
    ON hub.submission_audit_log (submission_id, created_at DESC);

CREATE OR REPLACE FUNCTION hub.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION hub.validate_category_tree()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_parent_id BIGINT;
BEGIN
    IF NEW.parent_id IS NULL THEN
        IF NEW.code_prefix IS NOT NULL THEN
            RAISE EXCEPTION '一级类目 code_prefix 必须为空' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    SELECT parent_id INTO parent_parent_id
      FROM hub.category
     WHERE id = NEW.parent_id
     FOR KEY SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION '父类目 % 不存在', NEW.parent_id USING ERRCODE = '23503';
    END IF;
    IF parent_parent_id IS NOT NULL THEN
        RAISE EXCEPTION '类目树固定两层，父类目必须是一级类目' USING ERRCODE = '23514';
    END IF;
    IF NEW.code_prefix IS NULL OR btrim(NEW.code_prefix) = '' THEN
        RAISE EXCEPTION '二级类目必须设置 code_prefix' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND EXISTS (
        SELECT 1 FROM hub.category child WHERE child.parent_id = OLD.id
    ) THEN
        RAISE EXCEPTION '含子类目的一级类目不能改为二级类目' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION hub.guard_category_numbering()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.seq_counter < OLD.seq_counter THEN
        RAISE EXCEPTION 'seq_counter 只增不减' USING ERRCODE = '23514';
    END IF;
    IF OLD.seq_counter > 0 AND NEW.code_prefix IS DISTINCT FROM OLD.code_prefix THEN
        RAISE EXCEPTION '已取号类目的 code_prefix 不可修改' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION hub.validate_sku_category()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    category_prefix VARCHAR(16);
BEGIN
    SELECT code_prefix INTO category_prefix
      FROM hub.category
     WHERE id = NEW.category_id
       AND parent_id IS NOT NULL
       AND is_active = TRUE
     FOR KEY SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'SKU 必须挂在启用的二级类目上' USING ERRCODE = '23514';
    END IF;
    IF NEW.sku_code !~ ('^' || category_prefix || '-[1-9][0-9]*$') THEN
        RAISE EXCEPTION '货号 % 与类目前缀 % 不匹配', NEW.sku_code, category_prefix USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION hub.prevent_active_sku_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.code_status = 'active' THEN
        RAISE EXCEPTION '正式货号不可删除，只能停用' USING ERRCODE = '23514';
    END IF;
    RETURN OLD;
END;
$$;

CREATE OR REPLACE FUNCTION hub.validate_submission_line()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    linked_status VARCHAR(16);
    linked_active BOOLEAN;
    linked_category_id BIGINT;
    linked_sku_code VARCHAR(64);
    new_category_valid BOOLEAN;
BEGIN
    IF NEW.is_new_item THEN
        SELECT EXISTS (
            SELECT 1 FROM hub.category
             WHERE id = NEW.category_id AND parent_id IS NOT NULL AND is_active = TRUE
        ) INTO new_category_valid;
        IF NOT new_category_valid THEN
            RAISE EXCEPTION '新品行 category_id 必须是启用的二级类目' USING ERRCODE = '23514';
        END IF;
    END IF;

    IF NEW.item_id IS NOT NULL THEN
        SELECT code_status, is_active, category_id, sku_code
          INTO linked_status, linked_active, linked_category_id, linked_sku_code
          FROM hub.sku
         WHERE id = NEW.item_id
         FOR KEY SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION '货号 % 不存在', NEW.item_id USING ERRCODE = '23503';
        END IF;
        IF NOT NEW.is_new_item AND (linked_status <> 'active' OR NOT linked_active) THEN
            RAISE EXCEPTION '老品行只能引用启用的正式货号' USING ERRCODE = '23514';
        END IF;
        IF NEW.is_new_item AND linked_category_id <> NEW.category_id THEN
            RAISE EXCEPTION '新品行货号与所选类目不一致' USING ERRCODE = '23514';
        END IF;
        IF NEW.is_new_item AND NEW.draft_sku_code IS NOT NULL
           AND NEW.draft_sku_code <> linked_sku_code THEN
            RAISE EXCEPTION 'draft_sku_code 与关联待审核货号不一致' USING ERRCODE = '23514';
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.qty_locked_at IS NOT NULL
       AND (NEW.qty IS DISTINCT FROM OLD.qty OR NEW.qty_locked_at IS DISTINCT FROM OLD.qty_locked_at) THEN
        RAISE EXCEPTION '已锁定数量不可修改' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION hub.validate_submission_status_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF NEW.status = 0 AND OLD.status BETWEEN 1 AND 3 THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 2 AND NEW.status = 1 THEN
        RETURN NEW;
    END IF;
    IF NEW.status = OLD.status + 1 AND OLD.status BETWEEN 1 AND 5 THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '非法提交单状态迁移：% -> %', OLD.status, NEW.status USING ERRCODE = '23514';
END;
$$;

CREATE OR REPLACE FUNCTION hub.ensure_submission_has_orders()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_id BIGINT;
BEGIN
    target_id := CASE WHEN TG_TABLE_NAME = 'submission' THEN NEW.id
                      WHEN TG_OP = 'DELETE' THEN OLD.submission_id
                      ELSE NEW.submission_id END;
    IF EXISTS (SELECT 1 FROM hub.submission WHERE id = target_id)
       AND NOT EXISTS (SELECT 1 FROM hub.submission_order WHERE submission_id = target_id) THEN
        RAISE EXCEPTION '提交单 % 至少需要一个订单', target_id USING ERRCODE = '23514';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION hub.ensure_order_has_lines()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_id BIGINT;
BEGIN
    target_id := CASE WHEN TG_TABLE_NAME = 'submission_order' THEN NEW.id
                      WHEN TG_OP = 'DELETE' THEN OLD.submission_order_id
                      ELSE NEW.submission_order_id END;
    IF EXISTS (SELECT 1 FROM hub.submission_order WHERE id = target_id)
       AND NOT EXISTS (SELECT 1 FROM hub.submission_line WHERE submission_order_id = target_id) THEN
        RAISE EXCEPTION '订单 % 至少需要一行明细', target_id USING ERRCODE = '23514';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION hub.prevent_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% 是只追加表，不允许 %', TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, TG_OP
        USING ERRCODE = '23514';
END;
$$;

CREATE OR REPLACE FUNCTION hub.next_sku_code(p_category_id BIGINT)
RETURNS VARCHAR(64)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, hub
AS $$
DECLARE
    generated_code VARCHAR(64);
BEGIN
    UPDATE hub.category
       SET seq_counter = seq_counter + 1,
           updated_at = clock_timestamp()
     WHERE id = p_category_id
       AND parent_id IS NOT NULL
       AND is_active = TRUE
       AND code_prefix IS NOT NULL
     RETURNING code_prefix || '-' || seq_counter INTO generated_code;

    IF generated_code IS NULL THEN
        RAISE EXCEPTION 'category_id % 必须是启用且有前缀的二级类目', p_category_id
            USING ERRCODE = '22023';
    END IF;
    RETURN generated_code;
END;
$$;

COMMENT ON FUNCTION hub.next_sku_code(BIGINT) IS
    '通过 UPDATE ... RETURNING 对类目行加锁并原子递增取号；号段只增不回收。';

DROP TRIGGER IF EXISTS trg_user_updated_at ON hub."user";
CREATE TRIGGER trg_user_updated_at BEFORE UPDATE ON hub."user"
FOR EACH ROW EXECUTE FUNCTION hub.set_updated_at();

DROP TRIGGER IF EXISTS trg_category_validate_tree ON hub.category;
CREATE TRIGGER trg_category_validate_tree BEFORE INSERT OR UPDATE OF parent_id, code_prefix ON hub.category
FOR EACH ROW EXECUTE FUNCTION hub.validate_category_tree();

DROP TRIGGER IF EXISTS trg_category_guard_numbering ON hub.category;
CREATE TRIGGER trg_category_guard_numbering BEFORE UPDATE OF seq_counter, code_prefix ON hub.category
FOR EACH ROW EXECUTE FUNCTION hub.guard_category_numbering();

DROP TRIGGER IF EXISTS trg_category_updated_at ON hub.category;
CREATE TRIGGER trg_category_updated_at BEFORE UPDATE ON hub.category
FOR EACH ROW EXECUTE FUNCTION hub.set_updated_at();

DROP TRIGGER IF EXISTS trg_sku_validate_category ON hub.sku;
CREATE TRIGGER trg_sku_validate_category BEFORE INSERT OR UPDATE OF sku_code, category_id ON hub.sku
FOR EACH ROW EXECUTE FUNCTION hub.validate_sku_category();

DROP TRIGGER IF EXISTS trg_sku_prevent_active_delete ON hub.sku;
CREATE TRIGGER trg_sku_prevent_active_delete BEFORE DELETE ON hub.sku
FOR EACH ROW EXECUTE FUNCTION hub.prevent_active_sku_delete();

DROP TRIGGER IF EXISTS trg_submission_validate_status ON hub.submission;
CREATE TRIGGER trg_submission_validate_status BEFORE UPDATE OF status ON hub.submission
FOR EACH ROW EXECUTE FUNCTION hub.validate_submission_status_transition();

DROP TRIGGER IF EXISTS trg_submission_updated_at ON hub.submission;
CREATE TRIGGER trg_submission_updated_at BEFORE UPDATE ON hub.submission
FOR EACH ROW EXECUTE FUNCTION hub.set_updated_at();

DROP TRIGGER IF EXISTS trg_submission_order_updated_at ON hub.submission_order;
CREATE TRIGGER trg_submission_order_updated_at BEFORE UPDATE ON hub.submission_order
FOR EACH ROW EXECUTE FUNCTION hub.set_updated_at();

DROP TRIGGER IF EXISTS trg_submission_line_validate ON hub.submission_line;
CREATE TRIGGER trg_submission_line_validate BEFORE INSERT OR UPDATE ON hub.submission_line
FOR EACH ROW EXECUTE FUNCTION hub.validate_submission_line();

DROP TRIGGER IF EXISTS trg_submission_line_updated_at ON hub.submission_line;
CREATE TRIGGER trg_submission_line_updated_at BEFORE UPDATE ON hub.submission_line
FOR EACH ROW EXECUTE FUNCTION hub.set_updated_at();

DROP TRIGGER IF EXISTS ctr_submission_has_orders_from_submission ON hub.submission;
CREATE CONSTRAINT TRIGGER ctr_submission_has_orders_from_submission
AFTER INSERT ON hub.submission DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION hub.ensure_submission_has_orders();

DROP TRIGGER IF EXISTS ctr_submission_has_orders_from_order ON hub.submission_order;
CREATE CONSTRAINT TRIGGER ctr_submission_has_orders_from_order
AFTER DELETE OR UPDATE OF submission_id ON hub.submission_order DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION hub.ensure_submission_has_orders();

DROP TRIGGER IF EXISTS ctr_order_has_lines_from_order ON hub.submission_order;
CREATE CONSTRAINT TRIGGER ctr_order_has_lines_from_order
AFTER INSERT ON hub.submission_order DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION hub.ensure_order_has_lines();

DROP TRIGGER IF EXISTS ctr_order_has_lines_from_line ON hub.submission_line;
CREATE CONSTRAINT TRIGGER ctr_order_has_lines_from_line
AFTER DELETE OR UPDATE OF submission_order_id ON hub.submission_line DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION hub.ensure_order_has_lines();

DROP TRIGGER IF EXISTS trg_inventory_ledger_immutable ON hub.inventory_ledger;
CREATE TRIGGER trg_inventory_ledger_immutable BEFORE UPDATE OR DELETE ON hub.inventory_ledger
FOR EACH ROW EXECUTE FUNCTION hub.prevent_mutation();

DROP TRIGGER IF EXISTS trg_sku_review_log_immutable ON hub.sku_review_log;
CREATE TRIGGER trg_sku_review_log_immutable BEFORE UPDATE OR DELETE ON hub.sku_review_log
FOR EACH ROW EXECUTE FUNCTION hub.prevent_mutation();

DROP TRIGGER IF EXISTS trg_submission_audit_log_immutable ON hub.submission_audit_log;
CREATE TRIGGER trg_submission_audit_log_immutable BEFORE UPDATE OR DELETE ON hub.submission_audit_log
FOR EACH ROW EXECUTE FUNCTION hub.prevent_mutation();

INSERT INTO hub.schema_migration(version)
VALUES ('001_hub_schema')
ON CONFLICT (version) DO NOTHING;

COMMIT;
