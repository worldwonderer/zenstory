"""
装饰器模块
"""
from .prefect import analysis_task, api_task, database_task, smart_retry_task

__all__ = ["smart_retry_task", "api_task", "database_task", "analysis_task"]
