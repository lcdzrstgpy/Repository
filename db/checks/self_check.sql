\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    missing_table TEXT;
    root_count INTEGER;
    child_count INTEGER;
    target_category_id BIGINT;
    before_counter INTEGER;
    first_code TEXT;
    second_code TEXT;
BEGIN
    SELECT expected.name
      INTO missing_table
      FROM (VALUES
          ('user'),
          ('category'),
          ('sku'),
          ('submission'),
          ('submission_order'),
          ('submission_line'),
          ('sku_review_log'),
          ('inventory_ledger'),
          ('webhook_dedup'),
          ('shipment_package'),
          ('submission_audit_log')
      ) AS expected(name)
     WHERE to_regclass(format('hub.%I', expected.name)) IS NULL
     LIMIT 1;

    IF missing_table IS NOT NULL THEN
        RAISE EXCEPTION '缺少 hub 表：%', missing_table;
    END IF;

    SELECT count(*) INTO root_count
      FROM hub.category
     WHERE parent_id IS NULL;
    SELECT count(*) INTO child_count
      FROM hub.category
     WHERE parent_id IS NOT NULL;

    IF root_count < 6 OR child_count < 13 THEN
        RAISE EXCEPTION '占位类目数量不足：一级 %，二级 %', root_count, child_count;
    END IF;

    IF EXISTS (
        SELECT prefix
          FROM unnest(ARRAY[
              'A001', 'A002', 'A003', 'B001', 'B002', 'C001', 'C002',
              'D001', 'D002', 'E001', 'E002', 'F001', 'F002'
          ]) AS expected(prefix)
         WHERE NOT EXISTS (
             SELECT 1 FROM hub.category
              WHERE code_prefix = expected.prefix AND parent_id IS NOT NULL
         )
    ) THEN
        RAISE EXCEPTION '占位二级类目不完整';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM hub.category child
          JOIN hub.category parent ON parent.id = child.parent_id
         WHERE child.parent_id IS NOT NULL
           AND (parent.parent_id IS NOT NULL OR child.code_prefix IS NULL)
    ) THEN
        RAISE EXCEPTION '类目树不是严格两层结构';
    END IF;

    SELECT id, seq_counter INTO target_category_id, before_counter
      FROM hub.category
     WHERE code_prefix = 'A001';

    first_code := hub.next_sku_code(target_category_id);
    second_code := hub.next_sku_code(target_category_id);

    IF first_code <> 'A001-' || (before_counter + 1)::TEXT
       OR second_code <> 'A001-' || (before_counter + 2)::TEXT THEN
        RAISE EXCEPTION '原子货号函数返回异常：%, %', first_code, second_code;
    END IF;

    BEGIN
        INSERT INTO hub.category(category_name, parent_id, code_prefix)
        SELECT '非法三级类目-自检', id, 'Z999'
          FROM hub.category
         WHERE code_prefix = 'A001';
        RAISE EXCEPTION '类目两层约束未生效';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    IF to_regprocedure('hub.next_sku_code(bigint)') IS NULL THEN
        RAISE EXCEPTION '缺少 hub.next_sku_code(bigint)';
    END IF;
END;
$$;

ROLLBACK;

SELECT
    current_setting('server_version_num')::INTEGER / 10000 AS postgres_major,
    (SELECT count(*) FROM hub.category WHERE parent_id IS NULL) AS root_categories,
    (SELECT count(*) FROM hub.category WHERE parent_id IS NOT NULL) AS child_categories,
    'ok' AS result;
