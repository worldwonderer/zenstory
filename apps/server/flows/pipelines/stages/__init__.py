#!/usr/bin/env python3
"""
阶段执行器模块

提供统一的阶段执行逻辑，消除主流程中的重复代码。
"""

from .stage_executor import StageExecutor

__all__ = [
    "StageExecutor",
]
