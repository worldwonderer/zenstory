#!/usr/bin/env python3
"""
别名规范化与合并工具（参考 deepscript）

提供：
- normalize_alias: 轻量规范化别名字符串
- merge_aliases: 合并并去重别名列表，保持稳定顺序（旧在前，新在后）
"""



def normalize_alias(alias: str | None) -> str:
    """
    对别名做轻量规范化，降低近似重复：
    - 去前后空格
    - 合并内部多余空格
    - 去除末尾常见冒号（半角/全角）
    - 去除常见称谓后缀

    Parameters
    ----------
    alias : Optional[str]
        原始别名字符串。

    Returns
    -------
    str
        规范化后的别名，None 或空输入返回空字符串。
    """
    if alias is None:
        return ""

    name = alias.strip()
    name = " ".join(name.split())
    name = name.rstrip("：:")

    # 去除常见称谓后缀（针对武侠小说）
    suffixes = ["公子", "姑娘", "师父", "老伯", "大人", "先生", "小姐"]
    for suffix in suffixes:
        if name.endswith(suffix) and len(name) > len(suffix):
            # 保留至少一个字的主名
            name = name[:-len(suffix)].strip()
            break

    return name


def merge_aliases(existing: list[str], incoming: list[str]) -> list[str]:
    """
    合并别名列表（规范化 + 去重 + 过滤单字），保持稳定顺序：旧在前，新在后。

    Parameters
    ----------
    existing : List[str]
        已有别名列表。
    incoming : List[str]
        新增别名列表。

    Returns
    -------
    List[str]
        合并后的去重别名列表（已过滤单字别名）。
    """
    norm_existing = [normalize_alias(a) for a in (existing or [])]
    norm_incoming = [normalize_alias(a) for a in (incoming or [])]

    seen: set[str] = set()
    merged: list[str] = []

    for a in norm_existing:
        # 【关键】过滤单字别名，避免误匹配风险（如"雷"）
        if a and a not in seen and len(a) >= 2:
            merged.append(a)
            seen.add(a)

    for a in norm_incoming:
        # 【关键】过滤单字别名，避免误匹配风险（如"雷"）
        if a and a not in seen and len(a) >= 2:
            merged.append(a)
            seen.add(a)

    return merged
