from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import AppError
from app.models.discovery import DiscoveryResult
from app.models.task import AuditTask, TaskAuditRequest, TaskStep
from app.services.infra.cache import CacheService
from app.services.infra.site_graph import SiteKnowledgeGraphService
from app.services.audit.content import ContentService
from app.services.discovery.discovery import DiscoveryService
from app.services.reporting.observation import ObservationService
from app.services.audit.page_content import PageContentAuditService
from app.services.audit.page_diagnostics import PageDiagnosticsService
from app.services.audit.platform import PlatformService
from app.services.audit.schema import SchemaService
from app.services.audit.summarizer import SummarizerService
from app.services.audit.technical import TechnicalService
from app.services.audit.visibility import VisibilityService
from app.utils.localization import localize_payload

logger = logging.getLogger(__name__)


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
    SITE_GEO_STEP_ORDER = ["discovery", "visibility", "technical", "content", "schema", "platform", "observation", "summary"]
    SITE_CONTENT_STEP_ORDER = ["discovery", "content", "summary"]

    def __init__(self) -> None:
        self.cache_service = CacheService()
        self.discovery_service = DiscoveryService()
        self.asset_store = self.discovery_service.asset_store
        self.site_graph_service = SiteKnowledgeGraphService()
        # 所有审计模块共享同一个 discovery_service 实例
        self.visibility_service = VisibilityService(self.discovery_service)
        self.technical_service = TechnicalService(self.discovery_service)
        self.content_service = ContentService(self.discovery_service)
        self.schema_service = SchemaService(self.discovery_service)
        self.platform_service = PlatformService(self.discovery_service)
        self.observation_service = ObservationService()
        self.page_content_audit_service = PageContentAuditService(self.discovery_service)
        self.page_diagnostics_service = PageDiagnosticsService()
        self.summarizer_service = SummarizerService()
        self.tasks: dict[str, AuditTask] = {}  # 内存任务存储
        self._lock = asyncio.Lock()             # 保护 tasks dict 的并发访问

    def _step_order_for(self, task_type: str) -> list[str]:
        if task_type == "site_content_audit":
            return list(self.SITE_CONTENT_STEP_ORDER)
        return list(self.SITE_GEO_STEP_ORDER)

    def _new_steps(self, step_order: list[str]) -> dict[str, TaskStep]:
        """初始化所有步骤为 pending 状态"""
        return {name: TaskStep(name=name) for name in step_order}

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
        for step_payload in payload.values():
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
                request.full_audit,
                request.max_pages,
                request.feedback_lang,
                request.task_type,
                request.target_locale,
            )
        except ValueError as exc:
            raise AppError(400, "invalid URL", str(exc)) from exc

        # force_refresh=True 时跳过缓存查询
        cached_record = None if request.force_refresh or request.observation else self.cache_service.get(cache_key)
        task_id = uuid4().hex
        now = self._utcnow()
        step_order = self._step_order_for(request.task_type)
        task = AuditTask(
            task_id=task_id,
            url=request.url,
            normalized_url=normalized_url,
            domain=domain,
            cache_key=cache_key,
            task_type=request.task_type,
            mode=request.mode,
            llm=request.llm,
            target_locale=request.target_locale,
            feedback_lang=request.feedback_lang,
            observation=request.observation,
            full_audit=request.full_audit,
            max_pages=request.max_pages,
            build_knowledge_graph=request.build_knowledge_graph,
            cached=bool(cached_record),
            force_refresh=request.force_refresh,
            storage_backend=self.asset_store.backend,
            created_at=now,
            updated_at=now,
            step_order=step_order,
            steps=self._new_steps(step_order),
        )

        # 缓存命中：直接从缓存构建已完成的任务
        if cached_record:
            for step_name in step_order:
                task.steps[step_name].status = "completed"
                task.steps[step_name].started_at = now
                task.steps[step_name].completed_at = now
                task.steps[step_name].data = cached_record.payload.get(step_name)
            task.status = "completed"
            task.current_step = "completed"
            task.progress_percent = 100
            task.completed_at = now
            task.result = cached_record.payload
            task.llm_model_used = self._detect_llm_model_used(cached_record.payload)
            discovery_payload = cached_record.payload.get("discovery") if isinstance(cached_record.payload, dict) else None
            if isinstance(discovery_payload, dict) and discovery_payload.get("asset_summary"):
                task.site_asset_summary = discovery_payload["asset_summary"]
                task.storage_backend = discovery_payload["asset_summary"].get("backend", task.storage_backend)
            self.tasks[task_id] = task
            if self.asset_store.available:
                try:
                    await self.asset_store.save_task(task)
                except Exception:
                    pass
            if request.build_knowledge_graph:
                await self._maybe_build_knowledge_graph_from_payload(task, cached_record.payload)
            return task

        # 新任务：注册后在后台启动审计协程
        async with self._lock:
            self.tasks[task_id] = task
        if self.asset_store.available:
            try:
                await self.asset_store.save_task(task)
            except Exception:
                pass
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
        """后台任务执行协程：按任务类型执行不同的审计流程。"""
        task = self.tasks[task_id]
        task.status = "running"
        task.current_step = task.step_order[0] if task.step_order else "running"
        task.updated_at = self._utcnow()
        if self.asset_store.available:
            try:
                await self.asset_store.save_task(task)
            except Exception:
                pass
        try:
            if task.task_type == "site_content_audit":
                task.result = await self._run_site_content_task(task)
            else:
                task.result = await self._run_site_geo_task(task)
            task.result = localize_payload(task.result, task.feedback_lang)
            for step_name in task.step_order:
                task.steps[step_name].data = task.result.get(step_name)
            task.llm_model_used = self._detect_llm_model_used(task.result)
            # 写入文件缓存，供后续相同请求直接命中
            if not getattr(task, "observation", None):
                self.cache_service.set(
                    task.cache_key,
                    url=task.url,
                    normalized_url=task.normalized_url,
                    domain=task.domain,
                    mode=task.mode,
                    feedback_lang=task.feedback_lang,
                    full_audit=task.full_audit,
                    max_pages=task.max_pages,
                    payload=task.result,
                    llm_config=task.llm,
                    task_type=task.task_type,
                    target_locale=task.target_locale,
                )
            task.status = "completed"
            task.current_step = "completed"
            task.progress_percent = 100
            task.completed_at = self._utcnow()
            task.updated_at = task.completed_at
            if self.asset_store.available:
                try:
                    await self.asset_store.save_task(task)
                except Exception:
                    pass
        except Exception as exc:
            # 任何步骤失败都标记整体任务失败
            task.status = "failed"
            task.error = str(exc)
            task.current_step = "failed"
            task.updated_at = self._utcnow()
            if self.asset_store.available:
                try:
                    await self.asset_store.save_task(task)
                except Exception:
                    pass

    async def _maybe_build_knowledge_graph(self, task: AuditTask, discovery: DiscoveryResult) -> None:
        if not task.build_knowledge_graph or not self.site_graph_service.enabled:
            logger.info(
                "Knowledge graph build skipped",
                extra={
                    "task_id": task.task_id,
                    "enabled": task.build_knowledge_graph,
                    "mysql_enabled": self.site_graph_service.enabled,
                    "reason": "disabled_by_request_or_mysql",
                },
            )
            return
        site_id = discovery.asset_summary.site_id if discovery.asset_summary else None
        if site_id is None:
            logger.info(
                "Knowledge graph build skipped",
                extra={
                    "task_id": task.task_id,
                    "enabled": task.build_knowledge_graph,
                    "mysql_enabled": self.site_graph_service.enabled,
                    "reason": "missing_site_id",
                },
            )
            return
        logger.info("Knowledge graph build started", extra={"task_id": task.task_id, "site_id": site_id})
        graph_summary = await self.site_graph_service.build(site_id=site_id, discovery=discovery, task_id=task.task_id)
        discovery.asset_summary.knowledge_graph = graph_summary
        task.site_asset_summary = discovery.asset_summary
        logger.info(
            "Knowledge graph build completed",
            extra={
                "task_id": task.task_id,
                "site_id": site_id,
                "built": graph_summary.built,
                "entity_count": graph_summary.entity_count,
                "edge_count": graph_summary.edge_count,
                "evidence_count": graph_summary.evidence_count,
                "note": graph_summary.note,
            },
        )

    async def _maybe_build_knowledge_graph_from_payload(self, task: AuditTask, payload: dict | None) -> None:
        if not task.build_knowledge_graph or not isinstance(payload, dict):
            return
        discovery_payload = payload.get("discovery")
        if not isinstance(discovery_payload, dict):
            return
        try:
            discovery = DiscoveryResult.model_validate(discovery_payload)
        except Exception:
            return
        site_id = discovery.asset_summary.site_id if discovery.asset_summary else None
        if site_id is not None and self.site_graph_service.enabled:
            graph_summary = await self.site_graph_service.ensure_task_snapshot(task_id=task.task_id, site_id=site_id)
            if graph_summary.built:
                discovery.asset_summary.knowledge_graph = graph_summary
                task.site_asset_summary = discovery.asset_summary
            else:
                await self._maybe_build_knowledge_graph(task, discovery)
        else:
            await self._maybe_build_knowledge_graph(task, discovery)
        if isinstance(task.result, dict):
            task.result["discovery"] = discovery.model_dump(mode="json")
        if self.asset_store.available:
            try:
                await self.asset_store.save_task(task)
            except Exception:
                pass

    async def _run_site_geo_task(self, task: AuditTask) -> dict:
        await self._update_step(task, "discovery", "running")
        discovery = await self.discovery_service.discover(
            task.url,
            full_audit=task.full_audit,
            max_pages=task.max_pages,
            force_refresh=task.force_refresh,
            target_locale=task.target_locale,
        )
        await self._maybe_build_knowledge_graph(task, discovery)
        discovery_payload = discovery.model_dump()
        task.site_asset_summary = discovery.asset_summary
        task.storage_backend = discovery.asset_summary.backend
        await self._update_step(task, "discovery", "completed", discovery_payload)

        module_coroutines = {
            "visibility": self.visibility_service.audit(
                task.url,
                discovery,
                mode=task.mode,
                llm_config=task.llm,
                feedback_lang=task.feedback_lang,
                target_locale=task.target_locale,
            ),
            "technical": self.technical_service.audit(
                task.url,
                discovery,
                mode=task.mode,
                llm_config=task.llm,
                target_locale=task.target_locale,
            ),
            "content": self.content_service.audit(
                task.url,
                discovery,
                mode=task.mode,
                llm_config=task.llm,
                feedback_lang=task.feedback_lang,
                target_locale=task.target_locale,
            ),
            "schema": self.schema_service.audit(
                task.url,
                discovery,
                mode=task.mode,
                llm_config=task.llm,
                target_locale=task.target_locale,
            ),
            "platform": self.platform_service.audit(
                task.url,
                discovery,
                mode=task.mode,
                llm_config=task.llm,
                feedback_lang=task.feedback_lang,
                target_locale=task.target_locale,
            ),
        }

        async def run_named(step_name: str, coroutine):
            result = await coroutine
            return step_name, result

        futures = []
        for step_name, coroutine in module_coroutines.items():
            await self._update_step(task, step_name, "running")
            futures.append(asyncio.create_task(run_named(step_name, coroutine)))

        module_results = {}
        for future in asyncio.as_completed(futures):
            step_name, result = await future
            module_results[step_name] = result
            await self._update_step(task, step_name, "completed", result.model_dump())

        await self._update_step(task, "observation", "running")
        observation_result = self.observation_service.build(task.observation)
        observation_payload = observation_result.model_dump()
        await self._update_step(task, "observation", "completed", observation_payload)

        await self._update_step(task, "summary", "running")
        summary = await self.summarizer_service.summarize(
            url=task.url,
            discovery=discovery,
            visibility=module_results["visibility"],
            technical=module_results["technical"],
            content=module_results["content"],
            schema=module_results["schema"],
            platform=module_results["platform"],
            observation=observation_result,
            mode=task.mode,
            llm_config=task.llm,
            feedback_lang=task.feedback_lang,
        )
        summary_payload = summary.model_dump()
        await self._update_step(task, "summary", "completed", summary_payload)
        page_diagnostics = self.page_diagnostics_service.build(discovery, max_pages=task.max_pages) if task.full_audit else []

        return {
            "url": task.url,
            "discovery": discovery_payload,
            "visibility": module_results["visibility"].model_dump(),
            "technical": module_results["technical"].model_dump(),
            "content": module_results["content"].model_dump(),
            "schema": module_results["schema"].model_dump(),
            "platform": module_results["platform"].model_dump(),
            "page_diagnostics": [item.model_dump() for item in page_diagnostics],
            "observation": observation_payload,
            "summary": summary_payload,
        }

    async def _run_site_content_task(self, task: AuditTask) -> dict:
        await self._update_step(task, "discovery", "running")
        discovery = await self.discovery_service.discover(
            task.url,
            full_audit=False,
            max_pages=5,
            force_refresh=task.force_refresh,
            target_locale=task.target_locale,
        )
        await self._maybe_build_knowledge_graph(task, discovery)
        discovery_payload = discovery.model_dump()
        task.site_asset_summary = discovery.asset_summary
        task.storage_backend = discovery.asset_summary.backend
        await self._update_step(task, "discovery", "completed", discovery_payload)

        await self._update_step(task, "content", "running")
        content = await self.page_content_audit_service.audit(
            task.url,
            discovery,
            mode=task.mode,
            llm_config=task.llm,
            feedback_lang=task.feedback_lang,
        )
        content_payload = content.model_dump()
        await self._update_step(task, "content", "completed", content_payload)

        await self._update_step(task, "summary", "running")
        summary = self.page_content_audit_service.summarize(
            discovery,
            content,
            feedback_lang=task.feedback_lang,
        )
        summary_payload = summary.model_dump()
        await self._update_step(task, "summary", "completed", summary_payload)

        return {
            "url": task.url,
            "discovery": discovery_payload,
            "content": content_payload,
            "summary": summary_payload,
        }
