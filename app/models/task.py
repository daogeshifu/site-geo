from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.requests import LLMConfig, UrlRequest

TaskStatus = Literal["queued", "running", "completed", "failed"]
StepStatus = Literal["pending", "running", "completed", "failed"]


class TaskAuditRequest(UrlRequest):
    force_refresh: bool = False


class TaskStep(BaseModel):
    name: str
    status: StepStatus = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    data: Any = None


class AuditTask(BaseModel):
    task_id: str
    url: str
    normalized_url: str
    domain: str
    cache_key: str
    mode: str = "standard"
    llm: LLMConfig | None = None
    status: TaskStatus = "queued"
    current_step: str = "queued"
    progress_percent: int = 0
    cached: bool = False
    force_refresh: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    steps: dict[str, TaskStep] = Field(default_factory=dict)
    result: dict[str, Any] | None = None


class CachedAuditRecord(BaseModel):
    cache_key: str
    url: str
    normalized_url: str
    domain: str
    mode: str
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: datetime
    expires_at: datetime
    payload: dict[str, Any]
