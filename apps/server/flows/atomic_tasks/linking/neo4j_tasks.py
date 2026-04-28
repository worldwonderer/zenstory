"""
Neo4j 图数据库任务

将人物关系写入 Neo4j 图数据库
"""

from typing import Any

from prefect import get_run_logger

from flows.database_session import get_db_session
from flows.utils.clients import get_neo4j_client
from flows.utils.decorators import database_task


@database_task(name="persist_chapter_relationships_to_neo4j", retries=3)
def persist_chapter_relationships_to_neo4j_task(
    novel_id: int,
    chapter_id: int,
) -> dict[str, Any]:
    """
    将章节的人物关系写入 Neo4j

    Args:
        novel_id: 小说ID
        chapter_id: 章节ID

    Returns:
        Dict: 写入结果统计
    """
    logger = get_run_logger()

    logger.info(f"开始写入 Neo4j: novel_id={novel_id}, chapter_id={chapter_id}")

    # 1. 从数据库获取人物关系
    from services.material.relationships_service import RelationshipsService
    with get_db_session() as db:
        # 注意：为确保每章都有完整快照，这里使用全量关系视图
        relationship_data = RelationshipsService().list_relationships_with_names(
            db, novel_id
        )

    logger.info(f"获取到 {len(relationship_data)} 个人物关系（全量快照）")

    # 2. 写入 Neo4j（对该章生成一次版本化快照）
    client = get_neo4j_client()
    result = client.persist_chapter_relationships(
        novel_id=novel_id,
        chapter_id=chapter_id,
        relationships=relationship_data,
    )

    logger.info(
        f"Neo4j 写入完成: skip={result.get('skip')}, "
        f"written={result.get('written')}"
    )

    return result


@database_task(name="persist_novel_relationships_to_neo4j", retries=3)
def persist_novel_relationships_to_neo4j_task(
    novel_id: int,
) -> dict[str, Any]:
    """
    将整本小说的人物关系写入 Neo4j

    Args:
        novel_id: 小说ID

    Returns:
        Dict: 写入结果统计
    """
    logger = get_run_logger()

    logger.info(f"开始写入整本小说的关系到 Neo4j: novel_id={novel_id}")

    # 1. 获取所有章节ID
    from services.material.chapters_service import ChaptersService
    with get_db_session() as db:
        chapters = ChaptersService().list_by_novel_ordered(db, novel_id)
        chapter_ids = [ch.id for ch in chapters]

    logger.info(f"找到 {len(chapter_ids)} 个章节")

    # 2. 逐章节写入
    total_written = 0
    total_skipped = 0

    for chapter_id in chapter_ids:
        result = persist_chapter_relationships_to_neo4j_task(
            novel_id=novel_id,
            chapter_id=chapter_id,
        )

        if result.get("skip"):
            total_skipped += 1
        else:
            total_written += result.get("written", 0)

    logger.info(
        f"整本小说 Neo4j 写入完成: "
        f"total_chapters={len(chapter_ids)}, "
        f"total_written={total_written}, "
        f"total_skipped={total_skipped}"
    )

    return {
        "novel_id": novel_id,
        "total_chapters": len(chapter_ids),
        "total_written": total_written,
        "total_skipped": total_skipped,
    }
