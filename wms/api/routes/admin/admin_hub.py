"""Hub（代发仓 ERP 中枢）仓库端接口的转发层。

Hub 的业务 API 用共享密钥 `X-WMS-Token` 认证。浏览器既不该也不能持有
这个密钥，所以由本层代理：

    admin 前端 → 本层（cookie 会话 + 页面权限）→ Hub

Hub 的响应（状态码 + JSON body）原样透传，前端拿到的错误结构与直连
Hub 时一致。只有 `_ALLOWED_PATHS` 白名单匹配的形状会被转发，避免这一层
被当成通往 Hub 任意接口的放大器。

Hub 仓库端接口全部挂在 /api/v1/warehouse 下，
见 backend/app/routers/warehouse.py。
"""

import logging
import os
import re

import requests
from flask import jsonify, request

from middleware.auth_middleware import require_admin_or_page_permission, require_auth
from routes.admin import admin_bp

_LOGGER = logging.getLogger(__name__)

_HUB_BASE_URL = os.environ.get("HUB_BASE_URL", "http://backend:8000").rstrip("/")
_HUB_WMS_TOKEN = os.environ.get("HUB_WMS_TOKEN", "").strip()
_HUB_TIMEOUT_SECONDS = float(os.environ.get("HUB_TIMEOUT_SECONDS", "10"))

# 精确到形状，不用前缀匹配 -- 前缀匹配会让 /submissions/1/anything 也能穿过去。
_ALLOWED_PATHS = (
    re.compile(r"^submissions$"),
    re.compile(r"^submissions/\d+/(verify|rework|dispatch)$"),
    re.compile(r"^submissions/\d+/lines/\d+/(change-item|merge-duplicate)$"),
    re.compile(r"^submissions/\d+/orders/\d+/cancel$"),
    re.compile(r"^skus/\d+/promote$"),
    re.compile(r"^catalog/categories$"),
    re.compile(r"^catalog/skus$"),
    re.compile(r"^catalog/skus/drafts$"),
    re.compile(r"^catalog/skus/search$"),
)


def _is_allowed(path):
    return any(pattern.match(path) for pattern in _ALLOWED_PATHS)


@admin_bp.route("/hub/<path:subpath>", methods=["GET", "POST"])
@require_auth
@require_admin_or_page_permission("hub-warehouse")
def hub_proxy(subpath):
    if not _is_allowed(subpath):
        return jsonify({"error": "hub_path_not_allowed", "path": subpath}), 404
    if not _HUB_WMS_TOKEN:
        # 未配置凭证时报 503 而不是透传 401：操作员能一眼看出这是部署问题，
        # 不是自己没权限。
        return jsonify({"error": "hub_token_not_configured"}), 503

    body = request.get_json(silent=True) if request.method == "POST" else None
    try:
        response = requests.request(
            request.method,
            f"{_HUB_BASE_URL}/api/v1/warehouse/{subpath}",
            json=body,
            params=request.args,
            headers={"X-WMS-Token": _HUB_WMS_TOKEN},
            timeout=_HUB_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        _LOGGER.warning("hub proxy could not reach %s: %s", subpath, exc)
        return jsonify({"error": "hub_unreachable", "detail": str(exc)}), 502

    try:
        payload = response.json()
    except ValueError:
        payload = {"error": "hub_invalid_response", "detail": response.text[:300]}
    return jsonify(payload), response.status_code
