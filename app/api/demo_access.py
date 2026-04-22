from __future__ import annotations

import hmac

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError


DEMO_TOKEN_HEADER = "X-Demo-Token"


def is_demo_token_enabled() -> bool:
    """当前环境是否启用了 demo token 保护。"""
    return bool(settings.demo_access_token)


def has_valid_demo_token(token: str | None) -> bool:
    """校验请求携带的 demo token。未启用时默认放行。"""
    expected = settings.demo_access_token
    if not expected:
        return True
    provided = (token or "").strip()
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def get_demo_token(request: Request) -> str | None:
    """从请求头读取 demo token。"""
    return request.headers.get(DEMO_TOKEN_HEADER)


def require_demo_token(request: Request) -> None:
    """在启用 demo token 时强制校验请求头。"""
    if has_valid_demo_token(get_demo_token(request)):
        return
    raise AppError(401, "demo token required or invalid")
