"""全局配置，全部从 .env 读取，未配置时使用默认值。"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ 目录（本文件位于 backend/app/core/config.py）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 加载 .env（不存在时静默跳过，使用下面的默认值）
load_dotenv(BASE_DIR / ".env")


def _get_bool(key: str, default: bool) -> bool:
    """读取布尔型配置，兼容 true/1/yes 等写法。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """应用配置项。"""

    # 应用
    APP_NAME: str = os.getenv("APP_NAME", "仓储管理系统")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = _get_bool("DEBUG", True)

    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:root@localhost:3306/warehouse_erp?charset=utf8mb4",
    )
    DB_ECHO: bool = _get_bool("DB_ECHO", False)

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "warehouse-erp-secret-key-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_DAYS: int = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

    # CORS，逗号分隔
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    # 分页
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "200"))


settings = Settings()
