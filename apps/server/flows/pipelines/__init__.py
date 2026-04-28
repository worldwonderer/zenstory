"""
流程编排模块
"""
# V3 流程 (推荐,简化的Pipeline模式)
from .novel_ingestion_v3_flow import novel_ingestion_v3

__all__ = [
    "novel_ingestion_v3",
]
