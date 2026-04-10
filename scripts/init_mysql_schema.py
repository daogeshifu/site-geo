from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.infra.mysql import pymysql


def main() -> None:
    if pymysql is None:
        raise RuntimeError("pymysql is not installed")

    if not settings.mysql_host or not settings.mysql_user:
        raise RuntimeError("MySQL environment variables are not configured")

    schema_path = Path(__file__).resolve().parents[1] / "sql" / "mysql" / "001_geo_asset_schema.sql"
    statements = [item.strip() for item in schema_path.read_text(encoding="utf-8").split(";") if item.strip()]
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=settings.mysql_connect_timeout_seconds,
        read_timeout=settings.mysql_read_timeout_seconds,
        write_timeout=settings.mysql_write_timeout_seconds,
    )
    try:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        connection.commit()
    finally:
        connection.close()

    print(f"Initialized MySQL schema from {schema_path}")


if __name__ == "__main__":
    main()
