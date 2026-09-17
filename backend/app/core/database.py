"""数据库连接与会话管理（SQLAlchemy 2.0 风格）。"""

from datetime import datetime
from typing import Generator

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings

# 连接池配置：pre_pool_ping 保证长时间空闲后连接可用
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有模型的基类。"""


class TimestampMixin:
    """统一时间戳字段：创建时间自动写入，更新时间自动刷新。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间"
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
