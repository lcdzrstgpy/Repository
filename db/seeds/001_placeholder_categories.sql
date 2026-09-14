\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    root_id BIGINT;
BEGIN
    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('家居用品', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('杯具', root_id, 'A001'),
        ('餐具', root_id, 'A002'),
        ('收纳', root_id, 'A003')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('厨房用品', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('锅具', root_id, 'B001'),
        ('小家电', root_id, 'B002')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('日用百货', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('清洁用品', root_id, 'C001'),
        ('纸品', root_id, 'C002')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('服饰配件', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('帽子', root_id, 'D001'),
        ('围巾', root_id, 'D002')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('宠物用品', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('食具', root_id, 'E001'),
        ('玩具', root_id, 'E002')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES ('文具', NULL, NULL)
    ON CONFLICT (category_name) WHERE parent_id IS NULL
    DO UPDATE SET is_active = TRUE
    RETURNING id INTO root_id;

    INSERT INTO hub.category (category_name, parent_id, code_prefix)
    VALUES
        ('笔类', root_id, 'F001'),
        ('本册', root_id, 'F002')
    ON CONFLICT (parent_id, category_name) WHERE parent_id IS NOT NULL
    DO UPDATE SET code_prefix = EXCLUDED.code_prefix, is_active = TRUE;
END;
$$;

INSERT INTO hub.schema_migration(version)
VALUES ('seed_001_placeholder_categories')
ON CONFLICT (version) DO NOTHING;

COMMIT;
