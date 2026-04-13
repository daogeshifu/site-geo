from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
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


@dataclass
class _ManagedConnection:
    connection: Any
    created_at: float


class _MySQLConnectionPool:
    """线程安全的轻量连接池，支持 pre-ping 和 recycle。"""

    def __init__(
        self,
        *,
        connect_fn,
        pool_size: int,
        max_overflow: int,
        pool_timeout_seconds: float,
        recycle_seconds: float,
        pre_ping: bool,
    ) -> None:
        self._connect_fn = connect_fn
        self.pool_size = max(1, pool_size)
        self.max_overflow = max(0, max_overflow)
        self.pool_timeout_seconds = max(0.1, pool_timeout_seconds)
        self.recycle_seconds = max(0.0, recycle_seconds)
        self.pre_ping = pre_ping
        self._idle: queue.LifoQueue[_ManagedConnection] = queue.LifoQueue(maxsize=self.pool_size)
        self._lock = threading.Lock()
        self._opened = 0

    def _close_connection(self, managed: _ManagedConnection) -> None:
        try:
            managed.connection.close()
        except Exception:
            pass
        with self._lock:
            self._opened = max(0, self._opened - 1)

    def _should_recycle(self, managed: _ManagedConnection) -> bool:
        return self.recycle_seconds > 0 and (time.monotonic() - managed.created_at) >= self.recycle_seconds

    def _is_connection_alive(self, managed: _ManagedConnection) -> bool:
        if not self.pre_ping:
            return True
        try:
            managed.connection.ping(reconnect=True)
            return True
        except Exception as exc:
            logger.warning("MySQL pooled connection ping failed", extra={"error": str(exc)})
            return False

    def _new_connection(self) -> _ManagedConnection:
        connection = self._connect_fn()
        return _ManagedConnection(connection=connection, created_at=time.monotonic())

    def acquire(self) -> _ManagedConnection:
        while True:
            try:
                managed = self._idle.get_nowait()
            except queue.Empty:
                managed = None

            if managed is not None:
                if self._should_recycle(managed):
                    logger.info("MySQL pooled connection recycled before checkout")
                    self._close_connection(managed)
                    continue
                if not self._is_connection_alive(managed):
                    self._close_connection(managed)
                    continue
                return managed

            with self._lock:
                can_open_new = self._opened < (self.pool_size + self.max_overflow)
                if can_open_new:
                    self._opened += 1
            if can_open_new:
                try:
                    return self._new_connection()
                except Exception:
                    with self._lock:
                        self._opened = max(0, self._opened - 1)
                    raise

            try:
                managed = self._idle.get(timeout=self.pool_timeout_seconds)
            except queue.Empty as exc:
                raise RuntimeError("Timed out waiting for a MySQL pooled connection.") from exc
            if self._should_recycle(managed):
                logger.info("MySQL pooled connection recycled after wait")
                self._close_connection(managed)
                continue
            if not self._is_connection_alive(managed):
                self._close_connection(managed)
                continue
            return managed

    def release(self, managed: _ManagedConnection, *, discard: bool = False) -> None:
        if discard:
            self._close_connection(managed)
            return

        try:
            if not getattr(managed.connection, "open", False):
                self._close_connection(managed)
                return
            self._idle.put_nowait(managed)
        except queue.Full:
            self._close_connection(managed)
        except Exception:
            self._close_connection(managed)


class MySQLClient:
    """轻量 MySQL 客户端，按需建立连接并通过线程池避免阻塞事件循环。"""

    _shared_pools: dict[tuple[Any, ...], _MySQLConnectionPool] = {}
    _pool_lock = threading.Lock()

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
        self.pool_size = max(1, settings.mysql_pool_size)
        self.pool_max_overflow = max(0, settings.mysql_pool_max_overflow)
        self.pool_timeout_seconds = max(0.1, settings.mysql_pool_timeout_seconds)
        self.pool_recycle_seconds = max(0.0, float(settings.mysql_pool_recycle_seconds))
        self.pool_pre_ping = settings.mysql_pool_pre_ping

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

    def _connect_sync(self):
        if not self.enabled or pymysql is None or DictCursor is None:
            raise RuntimeError("MySQL storage is not enabled")
        return pymysql.connect(
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

    def _pool_key(self) -> tuple[Any, ...]:
        return (
            settings.mysql_host,
            settings.mysql_port,
            settings.mysql_database,
            settings.mysql_user,
            settings.mysql_connect_timeout_seconds,
            settings.mysql_read_timeout_seconds,
            settings.mysql_write_timeout_seconds,
            self.pool_size,
            self.pool_max_overflow,
            self.pool_timeout_seconds,
            self.pool_recycle_seconds,
            self.pool_pre_ping,
        )

    def _get_pool(self) -> _MySQLConnectionPool:
        if not self.enabled:
            raise RuntimeError("MySQL storage is not enabled")
        pool_key = self._pool_key()
        with self._pool_lock:
            pool = self._shared_pools.get(pool_key)
            if pool is None:
                pool = _MySQLConnectionPool(
                    connect_fn=self._connect_sync,
                    pool_size=self.pool_size,
                    max_overflow=self.pool_max_overflow,
                    pool_timeout_seconds=self.pool_timeout_seconds,
                    recycle_seconds=self.pool_recycle_seconds,
                    pre_ping=self.pool_pre_ping,
                )
                self._shared_pools[pool_key] = pool
                logger.info(
                    "MySQL connection pool initialized",
                    extra={
                        "pool_size": self.pool_size,
                        "max_overflow": self.pool_max_overflow,
                        "pool_timeout_seconds": self.pool_timeout_seconds,
                        "pool_recycle_seconds": self.pool_recycle_seconds,
                        "pool_pre_ping": self.pool_pre_ping,
                    },
                )
            return pool

    @contextmanager
    def _connection(self):
        pool = self._get_pool()
        managed = pool.acquire()
        connection = managed.connection
        discard = False
        try:
            yield connection
            connection.commit()
        except Exception as exc:
            discard = self._is_retryable(exc)
            try:
                connection.rollback()
            except Exception:
                discard = True
            raise
        finally:
            pool.release(managed, discard=discard)

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
