"""
时间线任务

核心任务:
- extract_timeline_events_task: 从情节点提取时间线事件
- build_event_timeline_task: 构建事件时间线
"""

from typing import Any

from prefect import get_run_logger

from flows.database_session import get_prefect_db_session
from flows.utils.clients import LLMResponse, call_gemini_api, get_gemini_client
from flows.utils.decorators import api_task, database_task
from prompts import create_timeline_extraction_prompt


@api_task(name="extract_timeline_events", retries=5)
def extract_timeline_events_task(
    novel_id: int,
    chapter_ids: list[int] = None,
) -> dict[str, Any]:
    """
    从情节点提取时间线事件

    Args:
        novel_id: 小说ID
        chapter_ids: 章节ID列表(可选)

    Returns:
        Dict: 时间线事件提取结果
    """
    logger = get_run_logger()

    logger.info(f"开始提取时间线事件: novel_id={novel_id}")

    # 1. 获取情节点
    from services.material.timeline_service import TimelineService
    with get_prefect_db_session() as session:
        svc = TimelineService()
        plots = svc.list_plots_by_chapters(session, novel_id, chapter_ids)
        # 构建上下文
        context_parts = []
        plot_map = {}
        for plot in plots:
            context_parts.append(
                f"[情节点{plot.id}] 章节{plot.chapter.chapter_number}: {plot.description}"
            )
            plot_map[plot.id] = plot
        context = "\n".join(context_parts)

    logger.info(f"获取 {len(plots)} 个情节点用于时间线提取")

    # 2. 构建提示词
    system_prompt = create_timeline_extraction_prompt()

    # 3. 调用 LLM
    messages = [
        {
            "role": "user",
            "content": f"""
请从以下情节点中提取时间线事件:

{context}

请为每个情节点提取时间标签并排序。
""",
        }
    ]

    response: LLMResponse = call_gemini_api(messages, system_prompt)

    # 4. 提取和验证 JSON
    client = get_gemini_client()
    data = client.extract_json_from_response(response)

    timeline_events = data.get("timeline_events", [])

    logger.info(f"成功提取 {len(timeline_events)} 个时间线事件")

    return {
        "timeline_events": timeline_events,
        "novel_id": novel_id,
        "total_count": len(timeline_events),
    }


@database_task(name="build_event_timeline", retries=3)
def build_event_timeline_task(
    timeline_data: dict[str, Any],
    novel_id: int,
) -> dict[str, Any]:
    """
    构建事件时间线并入库

    Args:
        timeline_data: 时间线事件提取结果
        novel_id: 小说ID

    Returns:
        Dict: 入库结果统计
    """
    logger = get_run_logger()

    timeline_events = timeline_data.get("timeline_events", [])
    created_count = 0

    from services.material.timeline_service import TimelineService
    with get_prefect_db_session() as session:
        svc = TimelineService()
        created_count = svc.rebuild_timeline(session, novel_id, timeline_events)
        session.commit()

    logger.info(f"事件时间线入库完成: 创建 {created_count}")

    return {
        "created_count": created_count,
    }
