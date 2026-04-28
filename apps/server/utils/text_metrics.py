"""Text metrics helpers shared by backend services."""

from __future__ import annotations

import re

_CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fa5]")
_LATIN_TOKEN_PATTERN = re.compile(r"[a-zA-Z]+")


def count_words(content: str | None) -> int:
    """
    Count words with the same hybrid method used by the frontend.

    - Each Chinese character in U+4E00..U+9FA5 counts as 1 word
    - Each contiguous Latin letter sequence counts as 1 word
    - Numbers/symbols are not counted
    """
    if not content:
        return 0

    chinese_chars = len(_CHINESE_CHAR_PATTERN.findall(content))
    latin_tokens = len(_LATIN_TOKEN_PATTERN.findall(content))
    return chinese_chars + latin_tokens
