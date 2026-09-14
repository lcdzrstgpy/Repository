COMPOSE := docker compose
DB_SERVICE := db
DB_USER := $${POSTGRES_USER:-warehouse_erp}
DB_NAME := $${POSTGRES_DB:-warehouse_erp}

.PHONY: help config up app wms all hub-init down restart ps logs migrate seed db-shell db-check clean

help:
	@printf '%s\n' \
	  'make config    校验 Compose 配置' \
	  'make up        启动 PostgreSQL 16 并执行 hub 迁移与 seed' \
	  'make app       启动数据库、中枢后端和运营端' \
	  'make wms       启动数据库与 sentry-wms 全套服务' \
	  'make all       启动全部服务' \
	  'make hub-init  把中枢接入 sentry-wms（映射文件 + inbound 来源 allowlist）' \
	  'make migrate   重跑全部 hub 迁移与 seed（幂等）' \
	  'make db-check  执行数据库结构与约束自检' \
	  'make db-shell  进入 psql' \
	  'make logs      跟随全部服务日志' \
	  'make down      停止服务（保留数据卷）' \
	  'make clean     停止服务并删除数据卷'

config:
	$(COMPOSE) config --quiet

up:
	$(COMPOSE) up -d $(DB_SERVICE)
	$(COMPOSE) run --rm db-migrate

app:
	$(COMPOSE) --profile app up -d

wms:
	$(COMPOSE) --profile wms up -d

all:
	$(COMPOSE) --profile app --profile wms up -d

hub-init:
	@test -f wms/db/mappings/hub.yaml || cp wms/db/mappings/hub.yaml.template wms/db/mappings/hub.yaml
	$(COMPOSE) --profile wms up -d
	$(COMPOSE) exec -T $(DB_SERVICE) sh -ec 'psql -v ON_ERROR_STOP=1 -U "$(DB_USER)" -d "$(DB_NAME)"' < wms/db/seed-hub-source.sql
	$(COMPOSE) restart wms
	@printf '%s\n' \
	  'hub 接入进度：' \
	  '  [完成] 入站映射 wms/db/mappings/hub.yaml 已就位（source_system=hub）' \
	  '  [完成] inbound_source_systems_allowlist 已注册 hub (internal_tool)' \
	  '  [完成] wms API 已重启，映射已加载' \
	  '还需手工两步（见 wms/docs/hub-integration.md §3 与 §6）：' \
	  '  1) Admin > Tokens 签发 token：source_system=hub，inbound_resources=items,sales_orders；' \
	  '     明文只显示一次，写入 .env 的 SENTRY_TOKEN= 后 make restart' \
	  '  2) Admin > Webhooks 建订阅指向 http://backend:8000/api/v1/webhooks/sentry，' \
	  '     event_types 见文档 §6；secret 写入 .env 的 WEBHOOK_SECRET=' \
	  '本机 HTTP 联调还需 SENTRY_ALLOW_HTTP_WEBHOOKS=true 与 SENTRY_ALLOW_INTERNAL_WEBHOOKS=true；生产必须 HTTPS。'

down:
	$(COMPOSE) --profile app --profile wms down

restart:
	$(COMPOSE) --profile app --profile wms restart

ps:
	$(COMPOSE) --profile app --profile wms ps

logs:
	$(COMPOSE) --profile app --profile wms logs -f --tail=200

migrate:
	$(COMPOSE) up -d $(DB_SERVICE)
	$(COMPOSE) run --rm db-migrate

seed:
	$(COMPOSE) up -d $(DB_SERVICE)
	$(COMPOSE) exec -T $(DB_SERVICE) sh -ec 'psql -v ON_ERROR_STOP=1 -U "$(DB_USER)" -d "$(DB_NAME)"' < db/seeds/001_placeholder_categories.sql

db-shell:
	$(COMPOSE) exec $(DB_SERVICE) sh -ec 'exec psql -U "$(DB_USER)" -d "$(DB_NAME)"'

db-check:
	$(COMPOSE) exec -T $(DB_SERVICE) sh -ec 'psql -v ON_ERROR_STOP=1 -U "$(DB_USER)" -d "$(DB_NAME)"' < db/checks/self_check.sql

clean:
	$(COMPOSE) --profile app --profile wms down --volumes --remove-orphans
