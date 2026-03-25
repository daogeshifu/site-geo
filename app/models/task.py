from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.audit import ObservationInput
from app.models.requests import LLMConfig, UrlRequest

# 任务状态枚举
TaskStatus = Literal["queued", "running", "completed", "failed"]
# 步骤状态枚举
StepStatus = Literal["pending", "running", "completed", "failed"]


class TaskAuditRequest(UrlRequest):
    """异步审计任务创建请求"""

    force_refresh: bool = False  # 是否强制跳过缓存重新执行
    observation: ObservationInput | None = None


class TaskStep(BaseModel):
    """单个审计步骤的状态跟踪（共 8 步：discovery + 5 模块 + observation + summary）"""

    name: str                               # 步骤名称
    status: StepStatus = "pending"          # 当前状态
    started_at: datetime | None = None      # 步骤开始时间
    completed_at: datetime | None = None    # 步骤完成时间
    error: str | None = None               # 失败时的错误信息
    data: Any = None                        # 步骤执行结果数据


class AuditTask(BaseModel):
    """异步审计任务的完整状态模型，存储于内存中"""

    task_id: str           # UUID 任务标识符
    url: str               # 原始输入 URL
    normalized_url: str    # 规范化 URL
    domain: str            # 目标域名
    cache_key: str         # SHA256 缓存键
    mode: str = "standard"
    llm: LLMConfig | None = None
    feedback_lang: str = "en"
    observation: ObservationInput | None = None
    full_audit: bool = False
    max_pages: int = 12
    status: TaskStatus = "queued"         # 任务整体状态
    current_step: str = "queued"          # 当前正在执行的步骤名称
    progress_percent: int = 0             # 完成进度百分比（0-100）
    cached: bool = False                  # 是否从缓存加载结果
    llm_model_used: bool = False          # 是否真正使用并生效了 llm.model
    force_refresh: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error: str | None = None              # 任务失败时的全局错误信息
    steps: dict[str, TaskStep] = Field(default_factory=dict)  # 各步骤状态
    result: dict[str, Any] | None = None  # 任务完成后的全量结果


class CachedAuditRecord(BaseModel):
    """缓存的审计记录，持久化到 .cache/audits/ 目录下的 JSON 文件"""

    cache_key: str
    url: str
    normalized_url: str
    domain: str
    mode: str
    feedback_lang: str = "en"
    full_audit: bool = False
    max_pages: int = 12
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: datetime
    expires_at: datetime     # TTL 过期时间，超过后缓存失效
    payload: dict[str, Any]  # 完整的审计结果 dict
