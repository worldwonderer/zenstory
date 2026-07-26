"""
Unit tests for ToolContext with contextvars isolation.
"""

import asyncio

import pytest

from agent.tools.mcp_tools import ToolContext


class TestToolContextBasic:
    """Basic functionality tests for ToolContext."""

    def test_set_and_get_context(self):
        """验证基本的 set/get 功能"""
        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
        )
        ctx = ToolContext._get_context()
        assert ctx["project_id"] == "project-1"
        assert ctx["user_id"] == "user-1"
        assert ctx["session_id"] == "session-1"

    def test_context_cleanup(self):
        """验证 clear_context 正确清理"""
        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
        )
        ToolContext.set_pending_empty_file("file-1", "test.md")

        # 验证设置成功
        assert ToolContext._get_context()["project_id"] == "project-1"
        assert ToolContext.has_pending_empty_file() is True

        # 清理
        ToolContext.clear_context()

        # 验证清理成功
        assert ToolContext._get_context() == {}
        assert ToolContext.get_pending_empty_file() is None
        assert ToolContext.has_pending_empty_file() is False


class TestToolContextPendingFile:
    """Tests for pending empty file tracking."""

    def test_set_pending_empty_file(self):
        """验证设置待写入空文件"""
        ToolContext.set_context(None, "user-1", "project-1", None)

        assert ToolContext.has_pending_empty_file() is False

        ToolContext.set_pending_empty_file("file-123", "新章节.md")

        assert ToolContext.has_pending_empty_file() is True
        pending = ToolContext.get_pending_empty_file()
        assert pending is not None
        assert pending["file_id"] == "file-123"
        assert pending["title"] == "新章节.md"

    def test_clear_pending_empty_file(self):
        """验证清除待写入空文件"""
        ToolContext.set_context(None, "user-1", "project-1", None)
        ToolContext.set_pending_empty_file("file-123", "test.md")

        assert ToolContext.has_pending_empty_file() is True

        ToolContext.clear_pending_empty_file()

        assert ToolContext.has_pending_empty_file() is False
        assert ToolContext.get_pending_empty_file() is None

    def test_pending_file_cleared_on_new_context(self):
        """验证设置新上下文时清除待写入文件"""
        ToolContext.set_context(None, "user-1", "project-1", None)
        ToolContext.set_pending_empty_file("file-123", "test.md")

        # 设置新上下文
        ToolContext.set_context(None, "user-2", "project-2", None)

        # 待写入文件应该被清除
        assert ToolContext.has_pending_empty_file() is False


class TestToolContextCrossTask:
    """待写入空文件标记必须跨 asyncio 任务可见。

    openai-agents SDK 为 run loop 和每次 function tool 调用各包一层
    asyncio.create_task，create_task 只拷贝 contextvars 快照，因此标记
    不能依赖子任务里的 ContextVar 重绑定传递。
    """

    @pytest.mark.asyncio
    async def test_pending_flag_set_in_nested_task_visible_in_parent(self):
        """两层嵌套子任务（模拟 SDK run-loop task + tool task）里设置的标记，父上下文必须可见"""
        ToolContext.set_context(None, "user-1", "project-1", None)
        try:

            async def tool_task():
                ToolContext.set_pending_empty_file("file-1", "第1章.md")

            async def run_loop_task():
                await asyncio.create_task(tool_task())

            await asyncio.create_task(run_loop_task())

            assert ToolContext.has_pending_empty_file() is True
            pending = ToolContext.get_pending_empty_file()
            assert pending == {"file_id": "file-1", "title": "第1章.md"}
        finally:
            ToolContext.clear_context()

    @pytest.mark.asyncio
    async def test_clear_in_parent_visible_in_later_child_task(self):
        """父上下文清除标记后，后续子任务（如下一次 create_file 工具调用）必须读到已清除"""
        ToolContext.set_context(None, "user-1", "project-1", None)
        try:

            async def set_task():
                ToolContext.set_pending_empty_file("file-1", "第1章.md")

            await asyncio.create_task(set_task())
            assert ToolContext.has_pending_empty_file() is True

            ToolContext.clear_pending_empty_file()

            seen: list[bool] = []

            async def read_task():
                seen.append(ToolContext.has_pending_empty_file())

            await asyncio.create_task(read_task())
            assert seen == [False]
            assert ToolContext.has_pending_empty_file() is False
        finally:
            ToolContext.clear_context()

    @pytest.mark.asyncio
    async def test_pending_flag_set_in_gather_subtask_visible_to_siblings_and_parent(self):
        """asyncio.gather 子任务里设置的标记，兄弟任务与父上下文都必须可见"""
        ToolContext.set_context(None, "user-1", "project-1", None)
        try:
            sibling_saw: list[bool] = []

            async def setter():
                ToolContext.set_pending_empty_file("file-a", "并行文件.md")

            async def reader():
                await asyncio.sleep(0.05)
                sibling_saw.append(ToolContext.has_pending_empty_file())

            await asyncio.gather(setter(), reader())

            assert sibling_saw == [True]
            assert ToolContext.has_pending_empty_file() is True
        finally:
            ToolContext.clear_context()


class TestToolContextSession:
    """Tests for session management."""

    def test_get_session_from_context(self):
        """验证从上下文获取 session"""
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        ToolContext.set_context(
            session=mock_session,
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
        )

        session = ToolContext.get_session()
        assert session is mock_session

    def test_get_session_creates_new_if_needed(self):
        """验证在需要时创建新 session"""
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        create_func = MagicMock(return_value=mock_session)

        ToolContext.set_context(
            session=None,  # 不提供 session
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
            create_session_func=create_func,
        )

        session = ToolContext.get_session()

        assert session is mock_session
        create_func.assert_called_once()

    def test_get_session_raises_if_unavailable(self):
        """验证无 session 时抛出异常"""
        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
            create_session_func=None,  # 也不提供创建函数
        )

        with pytest.raises(RuntimeError, match="No session available"):
            ToolContext.get_session()
