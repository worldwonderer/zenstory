"""
世界观任务

核心任务:
- extract_world_view_task: 提取世界观信息
- update_world_view_task: 增量更新世界观
"""

from typing import Any

from prefect import get_run_logger

from flows.database_session import get_prefect_db_session
from flows.utils.clients import LLMResponse, call_gemini_api, get_gemini_client
from flows.utils.decorators import api_task, database_task
from prompts import create_world_view_extraction_prompt


@api_task(name="extract_world_view", retries=5)
def extract_world_view_task(
    novel_content: str,
    novel_id: int,
) -> dict[str, Any]:
    """
    从小说文本中提取世界观信息

    Args:
        novel_content: 小说内容
        novel_id: 小说ID

    Returns:
        Dict: 世界观提取结果
    """
    logger = get_run_logger()

    logger.info(f"开始提取世界观: novel_id={novel_id}")

    # 构建系统提示词
    system_prompt = create_world_view_extraction_prompt()

    # 调用 LLM
    messages = [
        {
            "role": "user",
            "content": f"""
小说内容:
{novel_content}

请提取世界观信息。
""",
        }
    ]

    response: LLMResponse = call_gemini_api(messages, system_prompt)

    # 提取和验证 JSON
    client = get_gemini_client()
    data = client.extract_json_from_response(response)

    logger.info("成功提取世界观信息")

    return {
        "world_view": data,
        "novel_id": novel_id,
    }


@database_task(name="update_world_view", retries=3)
def update_world_view_task(
    world_view_data: dict[str, Any],
    novel_id: int,
) -> dict[str, Any]:
    """
    增量更新世界观信息

    Args:
        world_view_data: 世界观提取结果
        novel_id: 小说ID

    Returns:
        Dict: 更新结果
    """
    logger = get_run_logger()

    world_view = world_view_data.get("world_view", {})

    from services.material.world_view_service import WorldViewService
    with get_prefect_db_session() as session:
        action = WorldViewService().upsert(session, novel_id, world_view)
        session.commit()
        logger.info("%s世界观" % ("创建" if action == "created" else "更新"))

    return {
        "action": action,
        "novel_id": novel_id,
    }
