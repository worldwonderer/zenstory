#!/usr/bin/env python3
"""
通用别名索引构建器（参考 deepscript）

提供：
- build_alias_index: 基于实体的主名与别名构建规范化键到实体的索引

通过 Protocol 限定实体具备 name 与 aliases 字段，避免与具体 ORM 模型耦合。
"""

from collections.abc import Iterable
from typing import Protocol, TypeVar

from .aliases import normalize_alias


class AliasEntity(Protocol):
    """
    具备名称与别名字段的实体协议。
    """

    name: str
    aliases: list[str] | None


T = TypeVar("T", bound=AliasEntity)


def build_alias_index(entities: Iterable[T]) -> dict[str, T]:  # noqa: UP047
    """
    构建"规范化主名/别名 -> 实体"的索引，用于快速归并匹配。

    Parameters
    ----------
    entities : Iterable[T]
        实体列表，需提供 name 与 aliases 字段。

    Returns
    -------
    Dict[str, T]
        规范化键到实体的映射。
    """
    index: dict[str, T] = {}
    for ent in entities:
        key = normalize_alias(ent.name)
        if key and key not in index:
            index[key] = ent
        for a in (ent.aliases or []):
            ak = normalize_alias(a)
            if ak and ak not in index:
                index[ak] = ent
    return index
