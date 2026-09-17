"""统一响应体与自定义业务异常。

响应格式（契约第二节）：
    {"code": 0, "msg": "ok", "data": {}}

错误码：
    0    成功
    400  参数错误
    401  未登录 / token 失效
    403  无权限
    404  资源不存在
    500  服务器内部错误
    1001 业务错误（如状态流转不合法），msg 为具体原因
"""

from typing import Any

from app.core.config import settings


class BizException(Exception):
    """业务异常，默认 code = 1001。"""

    def __init__(self, msg: str, code: int = 1001):
        self.code = code
        self.msg = msg
        super().__init__(msg)


class ParamException(BizException):
    """参数错误，code = 400。"""

    def __init__(self, msg: str = "参数错误"):
        super().__init__(msg, code=400)


class UnauthorizedException(BizException):
    """未登录 / token 失效，code = 401。"""

    def __init__(self, msg: str = "未登录或登录已过期，请重新登录"):
        super().__init__(msg, code=401)


class ForbiddenException(BizException):
    """无权限，code = 403。"""

    def __init__(self, msg: str = "无权限执行该操作"):
        super().__init__(msg, code=403)


class NotFoundException(BizException):
    """资源不存在，code = 404。"""

    def __init__(self, msg: str = "资源不存在"):
        super().__init__(msg, code=404)


def ok(data: Any = None, msg: str = "ok") -> dict:
    """成功响应。"""
    return {"code": 0, "msg": msg, "data": data}


def fail(code: int, msg: str, data: Any = None) -> dict:
    """失败响应。"""
    return {"code": code, "msg": msg, "data": data}


def paginate(items: list, total: int, page: int, page_size: int) -> dict:
    """分页数据结构。"""
    return {"list": items, "total": total, "page": page, "page_size": page_size}


def normalize_page(page: int | None, page_size: int | None) -> tuple[int, int]:
    """校正分页参数，避免非法值。"""
    page = 1 if not page or page < 1 else int(page)
    if not page_size or page_size < 1:
        page_size = settings.DEFAULT_PAGE_SIZE
    if page_size > settings.MAX_PAGE_SIZE:
        page_size = settings.MAX_PAGE_SIZE
    return page, page_size
