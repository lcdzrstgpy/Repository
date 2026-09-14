-- Hub ERP 接入：注册 hub 入站来源系统。
-- 幂等；须在 sentry-wms 的迁移（含 037_wms_tokens_inbound_columns）之后执行。
-- 由 `make hub-init` 调用。
\set ON_ERROR_STOP on

INSERT INTO inbound_source_systems_allowlist (source_system, kind, notes)
VALUES ('hub', 'internal_tool', '代发仓 ERP 中枢（FastAPI），推送 items / sales_orders')
ON CONFLICT (source_system) DO NOTHING;
