from __future__ import annotations

import logging
import logging.config

from pythonjsonlogger import jsonlogger

from app.core.config import settings


def configure_logging() -> None:
    if logging.getLogger().handlers:
        return

    class JsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
            super().add_fields(log_record, record, message_dict)
            log_record.setdefault("level", record.levelname)
            log_record.setdefault("logger", record.name)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                    "fmt": "%(asctime)s %(level)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": settings.log_level,
            },
        }
    )
