from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: Any = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    message: str
    errors: Any = None


def success_response(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return SuccessResponse(message=message, data=data).model_dump()


def error_response(message: str, errors: Any = None) -> dict[str, Any]:
    return ErrorResponse(message=message, errors=errors).model_dump()
