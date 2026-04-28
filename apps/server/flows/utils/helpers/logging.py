"""
日志辅助工具
"""
import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


def log_error_with_context(
    exc: Exception, message: str, logger: logging.Logger, **kwargs: Any
) -> None:
    """记录带上下文的错误日志"""
    logger.error(
        f"{message}: {str(exc)}",
        exc_info=True,
        extra=kwargs,
    )


def log_execution_time(task_name: str, elapsed: float, logger: logging.Logger) -> None:
    """记录任务执行时间"""
    logger.info(f"Task '{task_name}' completed in {elapsed:.3f}s")
