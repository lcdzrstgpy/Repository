"""认证接口（契约 5.1）：登录 / 当前用户 / 登出。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, ForbiddenException, ok
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.user import SysUser
from app.schemas.auth import LoginRequest
from app.schemas.serializers import user_info

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", summary="登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """校验用户名密码，签发有效期 7 天的 JWT。"""
    user = db.scalar(select(SysUser).where(SysUser.username == payload.username))
    # 用户不存在与密码错误返回同一提示，避免暴露账号是否存在
    if user is None or not verify_password(payload.password, user.password_hash):
        raise BizException("用户名或密码错误")
    if user.status != 1:
        raise ForbiddenException("账号已被停用，请联系管理员")

    token = create_access_token(user.id, user.username, user.role)
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": user_info(user),
        },
        msg="登录成功",
    )


@router.get("/me", summary="当前登录用户")
def me(current_user: SysUser = Depends(get_current_user)):
    """返回当前登录用户信息。"""
    return ok(user_info(current_user))


@router.post("/logout", summary="登出")
def logout(current_user: SysUser = Depends(get_current_user)):
    """JWT 无状态，服务端不维护会话，前端清除本地 token 即可。"""
    return ok(None, msg="已登出")
