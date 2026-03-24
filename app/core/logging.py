from __future__ import annotations

import logging
import logging.config

from pythonjsonlogger import jsonlogger

from app.core.config import settings


def configure_logging() -> None:
    """配置全局结构化 JSON 日志。

    - 幂等：若已有 handler 则跳过，避免重复注册
    - 自定义 JsonFormatter 在每条日志中注入 level 和 logger 字段，便于日志聚合平台过滤
    - 日志级别由 settings.log_level 控制（默认 INFO）
    """
    # 已有 handler 时直接返回，防止重复初始化
    if logging.getLogger().handlers:
        return

    class JsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
            """在 JSON 日志字段中补充 level 和 logger 字段"""
            super().add_fields(log_record, record, message_dict)
            log_record.setdefault("level", record.levelname)
            log_record.setdefault("logger", record.name)

    # 通过 dictConfig 统一配置日志处理器
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
