#!/usr/bin/env python3
"""
小说文本扫描工具（参考 deepscript）

提供：
- scan_chapter_for_aliases: 在章节中扫描出现的"规范化名字/别名键"
"""



def scan_chapter_for_aliases(
    chapter_content: str,
    candidate_keys: list[str],
    min_len: int = 2,
) -> set[str]:
    """
    在章节文本中扫描出现的"规范化名字/别名键"。

    策略：
    - 仅当键长度 >= min_len 时进行匹配（避免误匹配短别名如"他"、"她"）
    - 使用简单的包含式匹配

    Parameters
    ----------
    chapter_content : str
        章节文本内容。
    candidate_keys : List[str]
        候选的规范化键（通常是主名与别名）。
    min_len : int
        参与匹配的最小长度，默认 2。

    Returns
    -------
    Set[str]
        在文本中出现的键集合。
    """
    appeared: set[str] = set()
    text = chapter_content or ""
    if not text:
        return appeared

    # 包含式匹配（长度限制）
    for key in candidate_keys:
        if not key or len(key) < min_len:
            continue
        if key in text:
            appeared.add(key)

    return appeared
