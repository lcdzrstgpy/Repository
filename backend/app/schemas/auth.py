"""认证相关 schema（契约 5.1）。"""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=50, description="登录名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserInfo(BaseModel):
    """登录返回的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None = None
    role: str


class LoginResponse(BaseModel):
    """登录响应 data。"""

    access_token: str
    token_type: str = "bearer"
    user: UserInfo
