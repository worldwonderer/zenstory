"""
金手指实体任务

核心任务:
- extract_golden_fingers_task: 识别金手指/系统/外挂
- build_golden_finger_entities_task: 归一化金手指并建立实体
"""

from typing import Any

from prefect import get_run_logger

from flows.database_session import get_prefect_db_session
from flows.utils.clients import LLMResponse, call_gemini_api, get_gemini_client
from flows.utils.decorators import api_task, database_task
from prompts import create_golden_finger_extraction_prompt


@api_task(name="extract_golden_fingers", retries=5)
def extract_golden_fingers_task(
    novel_content: str,
    novel_id: int,
    chapter_range: str = "全文",
) -> dict[str, Any]:
    """
    从小说文本中识别金手指/系统/外挂

    Args:
        novel_content: 小说内容
        novel_id: 小说ID
        chapter_range: 章节范围

    Returns:
        Dict: 金手指提取结果
    """
    logger = get_run_logger()

    logger.info(f"开始提取金手指: novel_id={novel_id}")

    # 构建系统提示词
    system_prompt = create_golden_finger_extraction_prompt()

    # 调用 LLM
    messages = [
        {
            "role": "user",
            "content": f"""
章节范围: {chapter_range}

小说内容:
{novel_content}

请识别所有金手指/系统/外挂。
""",
        }
    ]

    response: LLMResponse = call_gemini_api(messages, system_prompt)

    # 提取和验证 JSON
    client = get_gemini_client()
    data = client.extract_json_from_response(response)

    golden_fingers = data.get("golden_fingers", [])

    logger.info(f"成功提取 {len(golden_fingers)} 个金手指")

    return {
        "golden_fingers": golden_fingers,
        "total_count": len(golden_fingers),
        "novel_id": novel_id,
    }


@database_task(name="build_golden_finger_entities", retries=3)
def build_golden_finger_entities_task(
    golden_fingers_data: dict[str, Any],
    novel_id: int,
    first_chapter_id: int = None,
) -> dict[str, Any]:
    """
    归一化金手指并建立实体入库

    Args:
        golden_fingers_data: 金手指提取结果
        novel_id: 小说ID
        first_chapter_id: 首次出现章节ID

    Returns:
        Dict: 入库结果
    """
    logger = get_run_logger()

    golden_fingers = golden_fingers_data.get("golden_fingers", [])
    created_count = 0
    updated_count = 0

    from services.material.golden_finger_service import GoldenFingerService
    with get_prefect_db_session() as session:
        svc = GoldenFingerService()
        for gf_data in golden_fingers:
            name = gf_data.get("name")
            if not name:
                continue
            action = svc.upsert(session, novel_id, {
                "name": name,
                "type": gf_data.get("type"),
                "description": gf_data.get("description"),
                "first_appearance_chapter_id": first_chapter_id,
            })
            if action == "created":
                created_count += 1
            elif action == "updated":
                updated_count += 1
        session.commit()

    logger.info(f"金手指入库完成: 创建 {created_count}, 更新 {updated_count}")

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "total_count": created_count + updated_count,
    }
