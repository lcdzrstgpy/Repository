import hmac

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def current_ops_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(
            token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except jwt.PyJWTError:
        raise credentials_error
    if payload.get("role") != "ops" or not payload.get("sub"):
        raise credentials_error
    user = await session.scalar(select(User).where(User.username == payload["sub"]))
    if user is None or not user.is_active or user.role != "ops":
        raise credentials_error
    return user


async def require_wms_token(
    x_wms_token: str | None = Header(default=None, alias="X-WMS-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_wms_token or not hmac.compare_digest(x_wms_token, settings.wms_api_token):
        raise HTTPException(status_code=401, detail="WMS 凭证无效")
