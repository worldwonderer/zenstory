"""
Concurrent isolation tests for ToolContext with contextvars.

These tests verify that multiple concurrent requests maintain
isolated contexts and don't interfere with each other.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from agent.tools.mcp_tools import ToolContext


class TestConcurrentIsolation:
    """Tests for concurrent request isolation."""

    @pytest.mark.asyncio
    async def test_concurrent_context_isolation(self):
        """
        验证并发请求之间的上下文隔离。

        重要：必须使用 asyncio.create_task() 创建独立任务，
        因为 contextvars 的隔离发生在任务边界。
        """
        results = []

        async def request_a():
            ToolContext.set_context(None, "user-a", "project-a", "session-a")
            await asyncio.sleep(0.1)  # 模拟 LLM 等待
            ctx = ToolContext._get_context()
            results.append(("A", ctx.get("project_id"), ctx.get("user_id")))

        async def request_b():
            await asyncio.sleep(0.05)  # 在 A 等待期间启动
            ToolContext.set_context(None, "user-b", "project-b", "session-b")
            ctx = ToolContext._get_context()
            results.append(("B", ctx.get("project_id"), ctx.get("user_id")))

        # 必须使用 create_task 创建独立任务以获得上下文隔离
        task_a = asyncio.create_task(request_a())
        task_b = asyncio.create_task(request_b())
        await asyncio.gather(task_a, task_b)

        # 验证：A 应该读到 project-a，B 应该读到 project-b
        result_a = next((r for r in results if r[0] == "A"), None)
        result_b = next((r for r in results if r[0] == "B"), None)

        assert result_a is not None, "Request A should have completed"
        assert result_b is not None, "Request B should have completed"
        assert result_a[1] == "project-a", f"A should see project-a, got {result_a[1]}"
        assert result_a[2] == "user-a", f"A should see user-a, got {result_a[2]}"
        assert result_b[1] == "project-b", f"B should see project-b, got {result_b[1]}"
        assert result_b[2] == "user-b", f"B should see user-b, got {result_b[2]}"

    @pytest.mark.asyncio
    async def test_pending_file_isolation(self):
        """验证待写入文件状态在并发请求间隔离。"""
        results = []

        async def request_a():
            ToolContext.set_context(None, "user-a", "project-a", None)
            ToolContext.set_pending_empty_file("file-a", "A的文件.md")
            await asyncio.sleep(0.1)
            pending = ToolContext.get_pending_empty_file()
            results.append(("A", pending))

        async def request_b():
            await asyncio.sleep(0.05)
            ToolContext.set_context(None, "user-b", "project-b", None)
            ToolContext.set_pending_empty_file("file-b", "B的文件.md")
            pending = ToolContext.get_pending_empty_file()
            results.append(("B", pending))

        task_a = asyncio.create_task(request_a())
        task_b = asyncio.create_task(request_b())
        await asyncio.gather(task_a, task_b)

        result_a = next((r for r in results if r[0] == "A"), None)
        result_b = next((r for r in results if r[0] == "B"), None)

        assert result_a is not None
        assert result_b is not None
        assert result_a[1]["file_id"] == "file-a", "A should see file-a"
        assert result_b[1]["file_id"] == "file-b", "B should see file-b"

    @pytest.mark.asyncio
    async def test_many_concurrent_requests(self):
        """验证大量并发请求的隔离。"""
        num_requests = 20
        results = {}

        async def make_request(request_id: int):
            project_id = f"project-{request_id}"
            user_id = f"user-{request_id}"

            ToolContext.set_context(None, user_id, project_id, None)

            # 随机延迟模拟真实场景
            await asyncio.sleep(0.01 * (request_id % 5))

            ctx = ToolContext._get_context()
            results[request_id] = {
                "expected_project": project_id,
                "actual_project": ctx.get("project_id"),
                "expected_user": user_id,
                "actual_user": ctx.get("user_id"),
            }

        # 创建所有任务
        tasks = [asyncio.create_task(make_request(i)) for i in range(num_requests)]
        await asyncio.gather(*tasks)

        # 验证所有请求都获得了正确的上下文
        for request_id, result in results.items():
            assert result["expected_project"] == result["actual_project"], \
                f"Request {request_id}: expected {result['expected_project']}, got {result['actual_project']}"
            assert result["expected_user"] == result["actual_user"], \
                f"Request {request_id}: expected {result['expected_user']}, got {result['actual_user']}"

    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """验证 session 在并发请求间隔离。"""
        results = []

        async def request_with_session(name: str):
            mock_session = MagicMock()
            mock_session.name = name

            ToolContext.set_context(
                session=mock_session,
                user_id=f"user-{name}",
                project_id=f"project-{name}",
                session_id=None,
            )

            await asyncio.sleep(0.05)

            session = ToolContext.get_session()
            results.append((name, session.name))

        task_a = asyncio.create_task(request_with_session("A"))
        task_b = asyncio.create_task(request_with_session("B"))
        await asyncio.gather(task_a, task_b)

        result_a = next((r for r in results if r[0] == "A"), None)
        result_b = next((r for r in results if r[0] == "B"), None)

        assert result_a is not None
        assert result_b is not None
        assert result_a[1] == "A", f"A should get session A, got {result_a[1]}"
        assert result_b[1] == "B", f"B should get session B, got {result_b[1]}"
