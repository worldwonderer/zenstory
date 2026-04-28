#!/usr/bin/env python3
"""
文本处理工具
"""


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Parameters
    ----------
    text : str
        原始文本
    max_length : int
        最大长度
    suffix : str
        截断后缀，默认 "..."

    Returns
    -------
    str
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
