from __future__ import annotations

from typing import Any


class AppError(Exception):
    """统一业务异常类，携带 HTTP 状态码、消息和可选错误详情"""

    def __init__(self, status_code: int, message: str, errors: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code  # HTTP 状态码，如 400、404、502 等
        self.message = message          # 面向客户端的错误消息
        self.errors = errors            # 可选的详细错误信息（字段校验错误等）
