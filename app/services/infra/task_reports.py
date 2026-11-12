"""Durable completed reports, independent of request-cache expiration."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.config import settings
from app.models.task import AuditTask

logger = logging.getLogger(__name__)
TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class TaskReportStore:
    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory or settings.task_report_dir)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, task: AuditTask) -> None:
        if task.status != "completed" or task.result is None:
            return
        if not TASK_ID_PATTERN.fullmatch(task.task_id):
            raise ValueError("Invalid task ID")
        # Steps repeat the complete result. Credentials are unnecessary to read
        # a finished report and must not become part of a saved share.
        content = task.model_dump_json(exclude={
            "steps": {"__all__": {"data"}},
            "llm": {"api_key", "base_url"},
        })
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                    suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            temporary.replace(self.directory / f"{task.task_id}.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get(self, task_id: str) -> AuditTask | None:
        if not TASK_ID_PATTERN.fullmatch(task_id):
            return None
        path = self.directory / f"{task_id}.json"
        try:
            task = AuditTask.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            logger.warning("Could not restore saved report", extra={"task_id": task_id})
            return None
        if task.task_id != task_id or task.status != "completed" or task.result is None:
            return None
        for name, step in task.steps.items():
            step.data = task.result.get(name)
        return task
