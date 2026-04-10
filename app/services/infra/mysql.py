from __future__ import annotations

import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Any

from app.core.config import settings

try:
    import pymysql
    from pymysql.cursors import DictCursor
    from pymysql.err import InterfaceError, OperationalError
except Exception:  # pragma: no cover - import failure is handled by enabled flag
    pymysql = None
    DictCursor = None
    InterfaceError = None
    OperationalError = None


logger = logging.getLogger(__name__)


class MySQLClient:
    """轻量 MySQL 客户端，按需建立连接并通过线程池避免阻塞事件循环。"""

    def __init__(self) -> None:
        self.enabled = bool(
            settings.mysql_enabled
            and settings.mysql_host
            and settings.mysql_database
            and settings.mysql_user
            and pymysql is not None
        )
        self.retry_attempts = max(1, settings.mysql_retry_attempts)
        self.retry_backoff_seconds = max(0.0, settings.mysql_retry_backoff_ms / 1000)

    def _is_retryable(self, exc: Exception) -> bool:
        if OperationalError is not None and isinstance(exc, OperationalError):
            code = exc.args[0] if exc.args else None
            return code in {2003, 2006, 2013, 2014, 2045, 2055}
        if InterfaceError is not None and isinstance(exc, InterfaceError):
            return True
        return False

    def _run_with_retry(self, fn, *args):
        last_exc: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return fn(*args)
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc) or attempt >= self.retry_attempts:
                    raise
                delay = self.retry_backoff_seconds * attempt
                logger.warning(
                    "MySQL operation failed, retrying",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self.retry_attempts,
                        "delay_seconds": delay,
                        "error": str(exc),
                    },
                )
                time.sleep(delay)
        if last_exc is not None:
            raise last_exc

    @contextmanager
    def _connection(self):
        if not self.enabled or pymysql is None or DictCursor is None:
            raise RuntimeError("MySQL storage is not enabled")
        connection = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=settings.mysql_connect_timeout_seconds,
            read_timeout=settings.mysql_read_timeout_seconds,
            write_timeout=settings.mysql_write_timeout_seconds,
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetchone_sync(self, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchone()

    def _fetchall_sync(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return list(cursor.fetchall() or [])

    def _execute_sync(self, sql: str, params: tuple[Any, ...] | None = None) -> int:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                return int(cursor.rowcount or 0)

    def _executemany_sync(self, sql: str, rows: list[tuple[Any, ...]]) -> int:
        if not rows:
            return 0
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
                return int(cursor.rowcount or 0)

    async def fetchone(self, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._run_with_retry, self._fetchone_sync, sql, params)

    async def fetchall(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._run_with_retry, self._fetchall_sync, sql, params)

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> int:
        return await asyncio.to_thread(self._run_with_retry, self._execute_sync, sql, params)

    async def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> int:
        return await asyncio.to_thread(self._run_with_retry, self._executemany_sync, sql, rows)

    async def healthcheck(self) -> bool:
        if not self.enabled:
            return False
        row = await self.fetchone("SELECT 1 AS ok")
        return bool(row and row.get("ok") == 1)
