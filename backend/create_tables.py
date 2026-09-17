"""建表脚本：创建数据库（若不存在）并执行 Base.metadata.create_all()。

用法：
    cd backend
    python3 create_tables.py

不使用 Alembic，表结构变更直接由 SQLAlchemy 模型驱动。
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.core.config import settings

# 必须先导入模型包，Base.metadata 才完整
from app.models import *  # noqa: F401,F403
from app.core.database import Base


def ensure_database() -> None:
    """MySQL：连接服务器（不指定库）并 CREATE DATABASE IF NOT EXISTS。"""
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "mysql" or not url.database:
        return

    import pymysql

    conn = pymysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username,
        password=url.password or "",
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
        conn.commit()
        print(f"[建库] 数据库 `{url.database}` 已就绪")
    finally:
        conn.close()


def create_tables() -> None:
    """按模型创建全部表，并补齐旧库所需的增量字段。"""
    engine = create_engine(settings.DATABASE_URL, echo=settings.DB_ECHO)
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "mysql":
        with engine.begin() as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'product_sku'"
                    )
                )
            }
            if "category_id" not in columns:
                connection.execute(text("ALTER TABLE product_sku ADD COLUMN category_id BIGINT NULL"))
                print("[升级] product_sku 已新增 category_id")
            purchase_columns = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order'"
                    )
                )
            }
            if "warehouse_id" not in purchase_columns:
                connection.execute(text("ALTER TABLE purchase_order ADD COLUMN warehouse_id BIGINT NULL"))
                print("[升级] purchase_order 已新增 warehouse_id")
            if "express_no" not in purchase_columns:
                connection.execute(text("ALTER TABLE purchase_order ADD COLUMN express_no VARCHAR(64) NULL"))
                print("[升级] purchase_order 已新增 express_no")
            supplier_nullable = connection.execute(
                text(
                    "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' "
                    "AND COLUMN_NAME = 'supplier_id'"
                )
            ).scalar()
            if supplier_nullable == "NO":
                connection.execute(text("ALTER TABLE purchase_order MODIFY COLUMN supplier_id BIGINT NULL"))
                print("[升级] purchase_order 已允许 supplier_id 为空")
    tables = ", ".join(sorted(Base.metadata.tables.keys()))
    print(f"[建表] 共 {len(Base.metadata.tables)} 张表：{tables}")
    engine.dispose()


def main() -> int:
    try:
        ensure_database()
        create_tables()
    except Exception as exc:  # noqa: BLE001
        print(f"[失败] 建表出错：{type(exc).__name__}: {exc}", file=sys.stderr)
        print("请检查 .env 中的 DATABASE_URL 是否正确、MySQL 是否已启动。", file=sys.stderr)
        return 1
    print("[完成] 建表结束，接下来可执行：python3 init_data.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
