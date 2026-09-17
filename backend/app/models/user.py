"""用户模型（契约 4.1 sys_user）。"""

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

# 角色中文名（契约 3.1）
ROLE_TEXT: dict[str, str] = {
    "admin": "管理员",
    "operator": "运营",
    "warehouse": "仓储",
    "approver": "审批",
}


class SysUser(Base, TimestampMixin):
    """系统用户。"""

    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="登录名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 哈希")
    real_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="姓名")
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="operator", comment="角色：admin/operator/warehouse/approver"
    )
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 启用 / 0 停用"
    )
