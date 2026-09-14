from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import current_ops_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserResponse
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = await session.scalar(select(User).where(User.username == body.username))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.role != "ops":
        raise HTTPException(status_code=403, detail="仅允许运营角色登录")
    token = create_access_token(
        subject=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        minutes=settings.access_token_minutes,
    )
    return TokenResponse(access_token=token, role=user.role)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(current_ops_user)):
    return UserResponse(id=user.id, username=user.username, role=user.role)
