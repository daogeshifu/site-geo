from __future__ import annotations

from app.services.infra.mysql import _MySQLConnectionPool


class _FakeConnection:
    def __init__(self, *, fail_ping: bool = False) -> None:
        self.fail_ping = fail_ping
        self.closed = False
        self.open = True

    def ping(self, reconnect: bool = True) -> None:
        if self.fail_ping:
            raise RuntimeError("ping failed")

    def close(self) -> None:
        self.closed = True
        self.open = False


def test_mysql_pool_reuses_idle_connection() -> None:
    created: list[_FakeConnection] = []

    def connect():
        connection = _FakeConnection()
        created.append(connection)
        return connection

    pool = _MySQLConnectionPool(
        connect_fn=connect,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=0.1,
        recycle_seconds=60,
        pre_ping=False,
    )

    first = pool.acquire()
    pool.release(first)
    second = pool.acquire()

    assert second.connection is first.connection
    assert len(created) == 1
    pool.release(second, discard=True)


def test_mysql_pool_discards_failed_ping_connection() -> None:
    created: list[_FakeConnection] = []

    def connect():
        connection = _FakeConnection()
        created.append(connection)
        return connection

    pool = _MySQLConnectionPool(
        connect_fn=connect,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=0.1,
        recycle_seconds=60,
        pre_ping=True,
    )

    first = pool.acquire()
    pool.release(first)
    first.connection.fail_ping = True

    second = pool.acquire()

    assert second.connection is not first.connection
    assert first.connection.closed is True
    assert len(created) == 2
    pool.release(second, discard=True)


def test_mysql_pool_recycles_stale_connection() -> None:
    created: list[_FakeConnection] = []

    def connect():
        connection = _FakeConnection()
        created.append(connection)
        return connection

    pool = _MySQLConnectionPool(
        connect_fn=connect,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=0.1,
        recycle_seconds=1,
        pre_ping=False,
    )

    first = pool.acquire()
    first.created_at -= 10
    pool.release(first)

    second = pool.acquire()

    assert second.connection is not first.connection
    assert first.connection.closed is True
    assert len(created) == 2
    pool.release(second, discard=True)
