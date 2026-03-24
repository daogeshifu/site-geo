from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import AppError
from app.models.task import AuditTask, TaskAuditRequest, TaskStep
from app.services.cache_service import CacheService
from app.services.content_service import ContentService
from app.services.discovery_service import DiscoveryService
from app.services.platform_service import PlatformService
from app.services.schema_service import SchemaService
from app.services.summarizer_service import SummarizerService
from app.services.technical_service import TechnicalService
from app.services.visibility_service import VisibilityService


class TaskService:
    """异步审计任务管理服务

    职责：
    - 创建并追踪审计任务（内存存储，重启后丢失）
    - 检查并返回缓存结果（支持 force_refresh 跳过）
    - 后台异步执行 7 步审计流程（discovery + 5模块 + summary）
    - 更新任务进度和步骤状态
    - 将完成的结果写入文件缓存
    """

    # 任务步骤的执行顺序
    STEP_ORDER = ["discovery", "visibility", "technical", "content", "schema", "platform", "summary"]

    def __init__(self) -> None:
        self.cache_service = CacheService()
        self.discovery_service = DiscoveryService()
        # 所有审计模块共享同一个 discovery_service 实例
        self.visibility_service = VisibilityService(self.discovery_service)
        self.technical_service = TechnicalService(self.discovery_service)
        self.content_service = ContentService(self.discovery_service)
        self.schema_service = SchemaService(self.discovery_service)
        self.platform_service = PlatformService(self.discovery_service)
        self.summarizer_service = SummarizerService()
        self.tasks: dict[str, AuditTask] = {}  # 内存任务存储
        self._lock = asyncio.Lock()             # 保护 tasks dict 的并发访问

    def _new_steps(self) -> dict[str, TaskStep]:
        """初始化所有步骤为 pending 状态"""
        return {name: TaskStep(name=name) for name in self.STEP_ORDER}

    def _utcnow(self) -> datetime:
        """获取当前 UTC 时间（带时区信息）"""
        return datetime.now(timezone.utc)

    def _progress(self, task: AuditTask) -> int:
        """计算任务完成百分比（completed 步骤数 / 总步骤数 * 100）"""
        completed = sum(1 for step in task.steps.values() if step.status == "completed")
        return int((completed / len(task.steps)) * 100)

    def _detect_llm_model_used(self, payload: dict | None) -> bool:
        """根据模块结果判断是否真正使用并生效了 LLM 增强。"""
        if not payload:
            return False
        for step_name in ("visibility", "technical", "content", "schema", "platform", "summary"):
            step_payload = payload.get(step_name)
            if isinstance(step_payload, dict) and step_payload.get("llm_enhanced") is True:
                return True
        return False

    async def create_task(self, request: TaskAuditRequest) -> AuditTask:
        """创建审计任务并触发后台执行

        流程：
        1. 生成缓存键并查询缓存（force_refresh 时跳过）
        2. 缓存命中：立即将所有步骤标记为 completed 并返回
        3. 缓存未命中：创建任务，注册到内存，启动后台协程
        """
        try:
            cache_key, normalized_url, domain = self.cache_service.build_cache_key(
                request.url,
                request.mode,
                request.llm,
            )
        except ValueError as exc:
            raise AppError(400, "invalid URL", str(exc)) from exc

        # force_refresh=True 时跳过缓存查询
        cached_record = None if request.force_refresh else self.cache_service.get(cache_key)
        task_id = uuid4().hex
        now = self._utcnow()
        task = AuditTask(
            task_id=task_id,
            url=request.url,
            normalized_url=normalized_url,
            domain=domain,
            cache_key=cache_key,
            mode=request.mode,
            llm=request.llm,
            cached=bool(cached_record),
            force_refresh=request.force_refresh,
            created_at=now,
            updated_at=now,
            steps=self._new_steps(),
        )

        # 缓存命中：直接从缓存构建已完成的任务
        if cached_record:
            for step_name in self.STEP_ORDER:
                task.steps[step_name].status = "completed"
                task.steps[step_name].started_at = now
                task.steps[step_name].completed_at = now
                # summary 步骤的数据键名为 "summary"，其他模块用步骤名
                if step_name == "summary":
                    task.steps[step_name].data = cached_record.payload.get("summary")
                else:
                    task.steps[step_name].data = cached_record.payload.get(step_name)
            task.status = "completed"
            task.current_step = "completed"
            task.progress_percent = 100
            task.completed_at = now
            task.result = cached_record.payload
            task.llm_model_used = self._detect_llm_model_used(cached_record.payload)
            self.tasks[task_id] = task
            return task

        # 新任务：注册后在后台启动审计协程
        async with self._lock:
            self.tasks[task_id] = task
        asyncio.create_task(self._run_task(task_id))
        return task

    async def get_task(self, task_id: str) -> AuditTask | None:
        """按 task_id 查询任务状态（线程安全）"""
        async with self._lock:
            return self.tasks.get(task_id)

    async def _update_step(
        self,
        task: AuditTask,
        step_name: str,
        status: str,
        data=None,
        error: str | None = None,
    ) -> None:
        """更新单个步骤的状态、时间戳和结果数据，并刷新任务进度"""
        step = task.steps[step_name]
        now = self._utcnow()
        if status == "running":
            step.started_at = step.started_at or now   # 只记录第一次开始时间
        if status in {"completed", "failed"}:
            step.completed_at = now
        step.status = status
        if data is not None:
            step.data = data
            if isinstance(data, dict) and data.get("llm_enhanced") is True:
                task.llm_model_used = True
        if error:
            step.error = error
        # 非 completed 状态时更新 current_step 指向当前步骤
        task.current_step = step_name if status != "completed" else task.current_step
        task.updated_at = now
        task.progress_percent = self._progress(task)

    async def _run_task(self, task_id: str) -> None:
        """后台任务执行协程：按步骤顺序执行完整审计流程

        执行顺序：
        1. discovery（串行）
        2. 5 个审计模块（并行，使用 asyncio.create_task + as_completed）
        3. summary（串行，依赖所有模块结果）
        4. 将结果写入文件缓存
        """
        task = self.tasks[task_id]
        task.status = "running"
        task.current_step = "discovery"
        task.updated_at = self._utcnow()
        try:
            # Step 1: 站点快照
            await self._update_step(task, "discovery", "running")
            discovery = await self.discovery_service.discover(task.url)
            discovery_payload = discovery.model_dump()
            await self._update_step(task, "discovery", "completed", discovery_payload)

            # Step 2-6: 5 个审计模块并行执行
            module_coroutines = {
                "visibility": self.visibility_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "technical": self.technical_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "content": self.content_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "schema": self.schema_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "platform": self.platform_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
            }

            async def run_named(step_name: str, coroutine):
                """包装协程，返回 (步骤名, 结果) 元组"""
                result = await coroutine
                return step_name, result

            # 先将所有模块标记为 running，再并行等待
            futures = []
            for step_name, coroutine in module_coroutines.items():
                await self._update_step(task, step_name, "running")
                futures.append(asyncio.create_task(run_named(step_name, coroutine)))

            # 使用 as_completed 实时更新每个完成的模块状态
            module_results = {}
            for future in asyncio.as_completed(futures):
                step_name, result = await future
                payload = result.model_dump()
                module_results[step_name] = result
                await self._update_step(task, step_name, "completed", payload)

            # Step 7: 汇总计算复合 GEO 分数
            await self._update_step(task, "summary", "running")
            summary = await self.summarizer_service.summarize(
                url=task.url,
                discovery=discovery,
                visibility=module_results["visibility"],
                technical=module_results["technical"],
                content=module_results["content"],
                schema=module_results["schema"],
                platform=module_results["platform"],
                mode=task.mode,
                llm_config=task.llm,
            )
            summary_payload = summary.model_dump()
            await self._update_step(task, "summary", "completed", summary_payload)

            # 组装完整结果
            task.result = {
                "url": task.url,
                "discovery": discovery_payload,
                "visibility": module_results["visibility"].model_dump(),
                "technical": module_results["technical"].model_dump(),
                "content": module_results["content"].model_dump(),
                "schema": module_results["schema"].model_dump(),
                "platform": module_results["platform"].model_dump(),
                "summary": summary_payload,
            }
            task.llm_model_used = self._detect_llm_model_used(task.result)
            # 写入文件缓存，供后续相同请求直接命中
            self.cache_service.set(
                task.cache_key,
                url=task.url,
                normalized_url=task.normalized_url,
                domain=task.domain,
                mode=task.mode,
                payload=task.result,
                llm_config=task.llm,
            )
            task.status = "completed"
            task.current_step = "completed"
            task.progress_percent = 100
            task.completed_at = self._utcnow()
            task.updated_at = task.completed_at
        except Exception as exc:
            # 任何步骤失败都标记整体任务失败
            task.status = "failed"
            task.error = str(exc)
            task.current_step = "failed"
            task.updated_at = self._utcnow()
