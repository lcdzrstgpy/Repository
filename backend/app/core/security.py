"""认证与鉴权：JWT 签发校验、密码哈希、当前用户依赖、角色依赖工厂。"""

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.response import ForbiddenException, UnauthorizedException

# bcrypt 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False：未带 token 时由我们自己抛 401，保证统一响应格式
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """生成 bcrypt 密码哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception:
        # 哈希格式非法等异常一律视为校验失败
        return False


def create_access_token(user_id: int, username: str, role: str) -> str:
    """签发 JWT，payload 含 user_id / username / role，有效期 7 天。"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解析 JWT，失败抛 401。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise UnauthorizedException("登录状态已失效，请重新登录")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """FastAPI 依赖：解析 Authorization 头，返回当前登录用户对象。"""
    # 延迟导入，避免 models 与 core 循环引用
    from app.models.user import SysUser

    if credentials is None or not credentials.credentials:
        raise UnauthorizedException("未提供登录凭证，请先登录")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise UnauthorizedException("登录凭证不完整，请重新登录")

    user = db.get(SysUser, int(user_id))
    if user is None:
        raise UnauthorizedException("用户不存在，请重新登录")
    if user.status != 1:
        raise ForbiddenException("账号已被停用，请联系管理员")
    return user


def require_roles(*roles: str) -> Callable:
    """角色依赖工厂。

    用法：
        @router.post("/xxx", dependencies=[Depends(require_roles("admin"))])

    传 "*" 或不传表示「任意已登录用户」。
    """

    def checker(current_user=Depends(get_current_user)):
        if not roles or "*" in roles:
            return current_user
        if current_user.role not in roles:
            raise ForbiddenException("无权限执行该操作，需要角色：" + " / ".join(roles))
        return current_user

    return checker
