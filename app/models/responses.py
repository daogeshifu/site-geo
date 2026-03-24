from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """标准成功响应结构，success 字段恒为 True"""

    success: Literal[True] = True
    message: str = "ok"
    data: Any = None  # 业务数据负载


class ErrorResponse(BaseModel):
    """标准错误响应结构，success 字段恒为 False"""

    success: Literal[False] = False
    message: str          # 错误消息
    errors: Any = None    # 详细错误信息（字段校验错误列表等）


def success_response(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """构建成功响应的 dict，供路由函数直接返回"""
    return SuccessResponse(message=message, data=data).model_dump()


def error_response(message: str, errors: Any = None) -> dict[str, Any]:
    """构建错误响应的 dict，供异常处理器使用"""
    return ErrorResponse(message=message, errors=errors).model_dump()
