"""
角色实体任务

核心任务:
- extract_characters_task: 从文本中识别人物提及
- build_character_entities_task: 清洗合并角色别名,生成角色实体
"""

from typing import Any

from prefect import get_run_logger

from flows.database_session import get_db_session
from flows.utils import (
    api_task,
    call_gemini_api,
    database_task,
    get_gemini_client,
)
from flows.utils.validators import validate_characters_response
from prompts import create_character_extraction_prompt


@api_task(name="extract_characters_from_chapter", retries=5)
def extract_characters_task(
    chapter_id: int,
) -> dict[str, Any]:
    """
    从章节中提取角色信息

    Args:
        chapter_id: 章节ID

    Returns:
        Dict: 角色提取结果
    """
    from flows.database_session import get_db_session

    logger = get_run_logger()

    logger.info(f"开始提取章节 {chapter_id} 的角色信息")

    # 获取章节内容
    from services.material.chapters_service import ChaptersService
    with get_db_session() as db:
        ch_svc = ChaptersService()
        ch = ch_svc.get_by_id(db, chapter_id)
        if not ch:
            raise ValueError(f"章节 {chapter_id} 不存在")

        novel_id = ch.novel_id
        novel_content = getattr(ch, "content", None) or getattr(ch, "original_content", "")
        chapter_range = f"第{ch.chapter_number}章"

    # 构建系统提示词
    system_prompt = create_character_extraction_prompt()

    # 调用 LLM
    user_message = f"""
章节范围: {chapter_range}

小说内容:
{novel_content}

请提取所有角色信息。
"""

    response = call_gemini_api(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt
    )

    # 提取 JSON
    client = get_gemini_client()
    data = client.extract_json_from_response(response)

    # 验证数据
    characters = validate_characters_response(data)

    logger.info(f"成功提取 {len(characters)} 个角色")

    return {
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "chapter_range": chapter_range,
        "characters": characters,
        "total_count": len(characters),
    }


@database_task(name="build_character_entities", retries=3)
def build_character_entities_task(
    novel_id: int,
    characters_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    清洗合并角色别名,生成角色实体并入库

    Args:
        novel_id: 小说ID
        characters_data: 章节角色提取结果列表

    Returns:
        Dict: 入库结果
    """
    logger = get_run_logger()

    # 汇总所有章节的角色
    all_characters = []
    for chapter_data in characters_data:
        all_characters.extend(chapter_data.get("characters", []))
    created_count = 0
    updated_count = 0

    logger.info(f"开始构建角色实体: 共 {len(all_characters)} 个角色")

    with get_db_session() as db:
        from services.material.characters_service import CharactersService
        created, updated = CharactersService().upsert_characters(
            db,
            novel_id,
            [
                {
                    "name": c.get("name"),
                    "aliases": c.get("aliases", []),
                    "description": c.get("description"),
                    "first_appearance_chapter_id": c.get("first_appearance_chapter_id"),
                }
                for c in all_characters
                if c.get("name")
            ],
        )
        created_count += created
        updated_count += updated
        db.commit()

    logger.info(f"角色入库完成: 创建 {created_count}, 更新 {updated_count}")

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "total_count": created_count + updated_count,
    }
