"""
Unit tests for ToolContext with contextvars isolation.
"""

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
