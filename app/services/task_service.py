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
    STEP_ORDER = ["discovery", "visibility", "technical", "content", "schema", "platform", "summary"]

    def __init__(self) -> None:
        self.cache_service = CacheService()
        self.discovery_service = DiscoveryService()
        self.visibility_service = VisibilityService(self.discovery_service)
        self.technical_service = TechnicalService(self.discovery_service)
        self.content_service = ContentService(self.discovery_service)
        self.schema_service = SchemaService(self.discovery_service)
        self.platform_service = PlatformService(self.discovery_service)
        self.summarizer_service = SummarizerService()
        self.tasks: dict[str, AuditTask] = {}
        self._lock = asyncio.Lock()

    def _new_steps(self) -> dict[str, TaskStep]:
        return {name: TaskStep(name=name) for name in self.STEP_ORDER}

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _progress(self, task: AuditTask) -> int:
        completed = sum(1 for step in task.steps.values() if step.status == "completed")
        return int((completed / len(task.steps)) * 100)

    async def create_task(self, request: TaskAuditRequest) -> AuditTask:
        try:
            cache_key, normalized_url, domain = self.cache_service.build_cache_key(
                request.url,
                request.mode,
                request.llm,
            )
        except ValueError as exc:
            raise AppError(400, "invalid URL", str(exc)) from exc
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
        if cached_record:
            for step_name in self.STEP_ORDER:
                task.steps[step_name].status = "completed"
                task.steps[step_name].started_at = now
                task.steps[step_name].completed_at = now
                if step_name == "summary":
                    task.steps[step_name].data = cached_record.payload.get("summary")
                else:
                    task.steps[step_name].data = cached_record.payload.get(step_name)
            task.status = "completed"
            task.current_step = "completed"
            task.progress_percent = 100
            task.completed_at = now
            task.result = cached_record.payload
            self.tasks[task_id] = task
            return task

        async with self._lock:
            self.tasks[task_id] = task
        asyncio.create_task(self._run_task(task_id))
        return task

    async def get_task(self, task_id: str) -> AuditTask | None:
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
        step = task.steps[step_name]
        now = self._utcnow()
        if status == "running":
            step.started_at = step.started_at or now
        if status in {"completed", "failed"}:
            step.completed_at = now
        step.status = status
        if data is not None:
            step.data = data
        if error:
            step.error = error
        task.current_step = step_name if status != "completed" else task.current_step
        task.updated_at = now
        task.progress_percent = self._progress(task)

    async def _run_task(self, task_id: str) -> None:
        task = self.tasks[task_id]
        task.status = "running"
        task.current_step = "discovery"
        task.updated_at = self._utcnow()
        try:
            await self._update_step(task, "discovery", "running")
            discovery = await self.discovery_service.discover(task.url)
            discovery_payload = discovery.model_dump()
            await self._update_step(task, "discovery", "completed", discovery_payload)

            module_coroutines = {
                "visibility": self.visibility_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "technical": self.technical_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "content": self.content_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "schema": self.schema_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
                "platform": self.platform_service.audit(task.url, discovery, mode=task.mode, llm_config=task.llm),
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
                payload = result.model_dump()
                module_results[step_name] = result
                await self._update_step(task, step_name, "completed", payload)

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
            task.status = "failed"
            task.error = str(exc)
            task.current_step = "failed"
            task.updated_at = self._utcnow()
