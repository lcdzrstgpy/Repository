"""FastAPI 应用入口：实例化、CORS、路由注册、全局异常处理。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, basic, data_io, inventory, order, purchase, stock, warehouse
from app.core.config import settings
from app.core.response import BizException, fail

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="公司内部仓储管理系统后端 · 一阶段：订单主链路（下单 / 接单 / 备货 / 发货即完成）",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------- CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- 全局异常处理
# 所有响应（含错误）统一为 {code, msg, data}，HTTP 状态码固定 200，业务码放在 body.code
def _json(code: int, msg: str, data=None) -> JSONResponse:
    return JSONResponse(status_code=200, content=fail(code, msg, data))


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    """业务异常：默认 code=1001，参数/未登录/无权限/不存在等由子类指定 code。"""
    return _json(exc.code, exc.msg)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 参数校验失败：code=400，msg 指出具体字段。"""
    details = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []) if part not in ("body", "query"))
        details.append(f"{loc}: {error.get('msg', '')}".strip(": "))
    msg = "参数校验失败：" + "；".join(details) if details else "参数校验失败"
    return _json(400, msg)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """框架层 HTTP 异常，映射到契约错误码。"""
    status_code = exc.status_code
    code = status_code if status_code in (400, 401, 403, 404, 405) else 500
    msg = {
        401: "未登录或登录已过期，请重新登录",
        403: "无权限访问该资源",
        404: "接口或资源不存在",
        405: "请求方法不被允许",
    }.get(status_code, str(exc.detail))
    return _json(code, msg)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底：未预期异常统一 code=500。"""
    if settings.DEBUG:
        # 开发环境把异常信息带回，便于定位
        return _json(500, f"服务器内部错误：{type(exc).__name__}: {exc}")
    return _json(500, "服务器内部错误")


# ---------------------------------------------------------------- 路由注册
app.include_router(auth.router)
basic.register_basic_routers(app)
app.include_router(order.router)
app.include_router(warehouse.router)
app.include_router(inventory.router)
app.include_router(stock.router)
purchase.register_purchase_routers(app)
app.include_router(data_io.router)
