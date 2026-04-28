"""
Tests for parallel execution tool.

Tests task execution, concurrency limits, and error handling.
"""

import asyncio
import json
from unittest.mock import patch

import pytest

from agent.tools.parallel_executor import (
    MAX_PARALLEL_TASKS,
    PARALLEL_EXECUTE_TOOL,
    PARALLEL_TASK_TYPES,
    SubagentTask,
    _make_error,
    _make_result,
    execute_parallel,
    handle_delete_file,
    handle_edit_file,
    handle_hybrid_search,
    handle_query_files,
    handle_write_chapter,
)


@pytest.mark.unit
class TestSubagentTask:
    """Test SubagentTask dataclass."""

    def test_task_creation(self):
        """Test creating a subagent task."""
        task = SubagentTask(
            id="task-1",
            task_type="write_chapter",
            description="Write chapter 1",
            parameters={"title": "Chapter 1"},
        )
        assert task.id == "task-1"
        assert task.task_type == "write_chapter"
        assert task.status == "pending"
        assert task.result is None
        assert task.error is None

    def test_task_with_result(self):
        """Test task with result."""
        task = SubagentTask(
            id="task-2",
            task_type="query_files",
            description="Query",
            parameters={},
            status="completed",
            result={"count": 5},
        )
        assert task.status == "completed"
        assert task.result == {"count": 5}


@pytest.mark.unit
class TestToolDefinition:
    """Test tool definition."""

    def test_tool_has_name(self):
        """Test tool has correct name."""
        assert PARALLEL_EXECUTE_TOOL["name"] == "parallel_execute"

    def test_tool_has_schema(self):
        """Test tool has input schema."""
        schema = PARALLEL_EXECUTE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "tasks" in schema["properties"]
        assert schema["properties"]["tasks"]["type"] == "array"

    def test_max_items_constraint(self):
        """Test max items constraint in schema."""
        tasks_schema = PARALLEL_EXECUTE_TOOL["input_schema"]["properties"]["tasks"]
        assert tasks_schema["maxItems"] == MAX_PARALLEL_TASKS

    def test_task_types_in_enum(self):
        """Test task types in enum."""
        task_item = PARALLEL_EXECUTE_TOOL["input_schema"]["properties"]["tasks"]["items"]
        task_type_enum = task_item["properties"]["type"]["enum"]
        assert list(PARALLEL_TASK_TYPES) == task_type_enum


@pytest.mark.unit
class TestMakeResult:
    """Test result formatting."""

    def test_make_result_dict(self):
        """Test making result from dict."""
        data = {"status": "success", "count": 5}
        result = _make_result(data)

        assert result["content"][0]["type"] == "text"
        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "success"
        assert parsed["count"] == 5

    def test_make_result_list(self):
        """Test making result from list."""
        data = [1, 2, 3]
        result = _make_result(data)

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed == [1, 2, 3]

    def test_make_result_unicode(self):
        """Test result handles unicode."""
        data = {"message": "中文测试"}
        result = _make_result(data)

        text = result["content"][0]["text"]
        assert "中文测试" in text


@pytest.mark.unit
class TestMakeError:
    """Test error formatting."""

    def test_make_error(self):
        """Test making error result."""
        result = _make_error("Something went wrong")

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert parsed["error"] == "Something went wrong"


@pytest.mark.asyncio
@pytest.mark.unit
class TestHandleWriteChapter:
    """Test write_chapter handler."""

    async def test_write_chapter_no_project(self):
        """Test write chapter without project context."""
        # Don't set any context - _get_context returns {}
        result = await handle_write_chapter({"title": "Test"})

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert "project_id" in parsed["error"]

    async def test_write_chapter_pending_file(self):
        """Test write chapter with pending file."""
        from agent.tools.mcp_tools import ToolContext

        # Set context with project_id
        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        # Set pending file
        ToolContext.set_pending_empty_file("file-1", "Pending.txt")

        try:
            result = await handle_write_chapter({"title": "Test"})

            text = result["content"][0]["text"]
            parsed = json.loads(text)
            assert parsed["status"] == "error"
            assert "previous file" in parsed["error"].lower()
        finally:
            ToolContext.clear_context()


@pytest.mark.asyncio
@pytest.mark.unit
class TestHandleEditFile:
    """Test edit_file handler."""

    async def test_edit_file_calls_mcp(self):
        """Test edit_file calls MCP tool."""
        with patch("agent.tools.mcp_tools.edit_file") as mock_edit:
            mock_edit.return_value = {"content": [{"type": "text", "text": '{"status": "ok"}'}]}

            await handle_edit_file({
                "file_id": "file-1",
                "operations": [{"op": "replace", "old": "a", "new": "b"}],
            })

            mock_edit.assert_called_once()
            call_args = mock_edit.call_args[0][0]
            assert call_args["id"] == "file-1"
            assert call_args["edits"] == [{"op": "replace", "old": "a", "new": "b"}]

    async def test_edit_file_supports_canonical_params(self):
        """handle_edit_file should accept canonical edit_file params (id/edits)."""
        with patch("agent.tools.mcp_tools.edit_file") as mock_edit:
            mock_edit.return_value = {"content": [{"type": "text", "text": '{"status": "ok"}'}]}

            result = await handle_edit_file({
                "id": "file-2",
                "edits": [{"op": "append", "text": "x"}],
            })

            assert result is not None
            mock_edit.assert_called_once()
            call_args = mock_edit.call_args[0][0]
            assert call_args["id"] == "file-2"
            assert call_args["edits"] == [{"op": "append", "text": "x"}]

    async def test_edit_file_missing_id_returns_error(self):
        """handle_edit_file should fail fast when id is missing."""
        result = await handle_edit_file({
            "operations": [{"op": "append", "text": "x"}],
        })

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert "missing" in parsed["error"].lower()


@pytest.mark.asyncio
@pytest.mark.unit
class TestHandleDeleteFile:
    """Test delete_file handler."""

    async def test_delete_file_calls_mcp(self):
        """Test delete_file forwards canonical params to MCP tool."""
        with patch("agent.tools.mcp_tools.delete_file") as mock_delete:
            mock_delete.return_value = {"content": [{"type": "text", "text": '{"status": "ok"}'}]}

            await handle_delete_file({
                "file_id": "file-1",
                "recursive": True,
            })

            mock_delete.assert_called_once_with({
                "id": "file-1",
                "recursive": True,
            })

    async def test_delete_file_missing_id_returns_error(self):
        """handle_delete_file should fail fast when id is missing."""
        result = await handle_delete_file({})

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert "missing" in parsed["error"].lower()


@pytest.mark.asyncio
@pytest.mark.unit
class TestHandleQueryFiles:
    """Test query_files handler."""

    async def test_query_files_no_project(self):
        """Test query without project context."""
        result = await handle_query_files({"query": "test"})

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert "project_id" in parsed["error"]


@pytest.mark.asyncio
@pytest.mark.unit
class TestHandleHybridSearch:
    """Test hybrid_search handler."""

    async def test_hybrid_search_no_project(self):
        """Test hybrid_search without project context."""
        result = await handle_hybrid_search({"query": "test"})

        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "error"
        assert "project_id" in parsed["error"]

    async def test_hybrid_search_calls_mcp(self):
        """Test hybrid_search forwards canonical params to MCP tool."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.mcp_tools.hybrid_search") as mock_search:
                mock_search.return_value = {"content": [{"type": "text", "text": '{"status": "ok"}'}]}

                result = await handle_hybrid_search({
                    "query": "hero",
                    "top_k": 5,
                    "entity_types": ["draft"],
                    "min_score": 0.3,
                })

                assert result is not None
                mock_search.assert_called_once_with({
                    "query": "hero",
                    "top_k": 5,
                    "entity_types": ["draft"],
                    "min_score": 0.3,
                })
        finally:
            ToolContext.clear_context()


@pytest.mark.asyncio
@pytest.mark.unit
class TestExecuteParallel:
    """Test parallel execution."""

    async def test_execute_empty_tasks(self):
        """Test executing empty task list."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            result = await execute_parallel([])

            text = result["content"][0]["text"]
            parsed = json.loads(text)
            assert parsed["status"] == "success"
            assert parsed["data"]["total_tasks"] == 0
        finally:
            ToolContext.clear_context()

    async def test_execute_limits_tasks(self):
        """Test that execution limits to MAX_PARALLEL_TASKS."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            # Create more tasks than limit
            tasks = [{"type": "query_files", "description": f"Query {i}", "params": {}} for i in range(10)]

            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{"count": 0}'}]}

                result = await execute_parallel(tasks)

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                # Should only execute MAX_PARALLEL_TASKS
                assert parsed["data"]["total_tasks"] == MAX_PARALLEL_TASKS
        finally:
            ToolContext.clear_context()

    async def test_execute_with_pending_file_error(self):
        """Test execution blocked by pending file."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        ToolContext.set_pending_empty_file("file-1", "Pending.txt")

        try:
            result = await execute_parallel([{"type": "query_files", "description": "Q", "params": {}}])

            text = result["content"][0]["text"]
            parsed = json.loads(text)
            assert parsed["status"] == "error"
            assert "pending" in parsed["error"].lower()
        finally:
            ToolContext.clear_context()

    async def test_execute_unknown_task_type(self):
        """Test execution with unknown task type."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            result = await execute_parallel([{"type": "unknown_type", "description": "X", "params": {}}])

            text = result["content"][0]["text"]
            parsed = json.loads(text)
            # Task should fail but execution should complete
            assert parsed["status"] == "success"
            assert parsed["data"]["any_failed"] is True
        finally:
            ToolContext.clear_context()

    async def test_execute_marks_failed_on_error_payload(self):
        """Test tasks are marked failed when MCP payload reports status=error."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {
                    "content": [{"type": "text", "text": '{"status":"error","error":"Query failed"}'}]
                }

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q1", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                task = parsed["data"]["tasks"][0]

                assert parsed["data"]["completed"] == 0
                assert parsed["data"]["failed"] == 1
                assert parsed["data"]["any_failed"] is True
                assert parsed["data"]["all_completed"] is False
                assert task["status"] == "failed"
                assert task["error"] == "Query failed"
        finally:
            ToolContext.clear_context()

    async def test_execute_supports_hybrid_search(self):
        """Test execution supports hybrid_search task type."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_hybrid_search") as mock_search:
                mock_search.return_value = {
                    "content": [{"type": "text", "text": '{"status":"success","data":{"items":[]}}'}]
                }

                result = await execute_parallel([
                    {"type": "hybrid_search", "description": "Search context", "params": {"query": "hero"}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                task = parsed["data"]["tasks"][0]

                assert parsed["data"]["completed"] == 1
                assert parsed["data"]["failed"] == 0
                assert parsed["data"]["all_completed"] is True
                assert task["type"] == "hybrid_search"
                assert task["status"] == "completed"
        finally:
            ToolContext.clear_context()

    async def test_execute_supports_delete_file(self):
        """Test execution supports delete_file task type."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_delete_file") as mock_delete:
                mock_delete.return_value = {
                    "content": [{"type": "text", "text": '{"status":"success","data":{"deleted":true}}'}]
                }

                result = await execute_parallel([
                    {"type": "delete_file", "description": "Delete a draft", "params": {"id": "file-1"}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                task = parsed["data"]["tasks"][0]

                assert parsed["data"]["completed"] == 1
                assert parsed["data"]["failed"] == 0
                assert parsed["data"]["all_completed"] is True
                assert task["type"] == "delete_file"
                assert task["status"] == "completed"
        finally:
            ToolContext.clear_context()


@pytest.mark.asyncio
@pytest.mark.integration
class TestParallelExecutionConcurrency:
    """Test concurrency behavior."""

    async def test_concurrency_limit(self):
        """Test that concurrency is limited to MAX_CONCURRENCY."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            execution_times = []

            async def slow_query(params):
                start = asyncio.get_event_loop().time()
                execution_times.append(start)
                await asyncio.sleep(0.1)
                return {"content": [{"type": "text", "text": '{"ok": true}'}]}

            tasks = [
                {"type": "query_files", "description": f"Query {i}", "params": {}}
                for i in range(4)
            ]

            with patch("agent.tools.parallel_executor.handle_query_files", side_effect=slow_query):
                start_time = asyncio.get_event_loop().time()
                await execute_parallel(tasks)
                total_time = asyncio.get_event_loop().time() - start_time

                # With MAX_CONCURRENCY=2 and 4 tasks of 0.1s each,
                # total time should be ~0.2s (2 batches), not 0.4s (sequential)
                # or 0.1s (unlimited parallel)
                assert total_time >= 0.15  # At least 2 batches
                assert total_time < 0.35  # Not fully sequential
        finally:
            ToolContext.clear_context()

    async def test_all_complete_on_success(self):
        """Test all_completed flag on success."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{"ok": true}'}]}

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q1", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                assert parsed["data"]["all_completed"] is True
                assert parsed["data"]["any_failed"] is False
        finally:
            ToolContext.clear_context()

    async def test_any_failed_on_error(self):
        """Test any_failed flag on error."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.side_effect = Exception("Query failed")

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q1", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                assert parsed["data"]["any_failed"] is True
                assert parsed["data"]["completed"] == 0
                assert parsed["data"]["failed"] == 1
        finally:
            ToolContext.clear_context()

    async def test_task_status_tracking(self):
        """Test task status is tracked correctly."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{"ok": true}'}]}

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q1", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)
                task = parsed["data"]["tasks"][0]
                assert task["status"] == "completed"
                assert task["result"] == {"ok": True}
        finally:
            ToolContext.clear_context()


@pytest.mark.asyncio
@pytest.mark.integration
class TestParallelExecutionResults:
    """Test result aggregation."""

    async def test_result_aggregation(self):
        """Test results are properly aggregated."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{"count": 5}'}]}

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q1", "params": {"query": "a"}},
                    {"type": "query_files", "description": "Q2", "params": {"query": "b"}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)

                assert parsed["data"]["total_tasks"] == 2
                assert parsed["data"]["completed"] == 2
                assert len(parsed["data"]["tasks"]) == 2

                # Each task should have its result
                for task in parsed["data"]["tasks"]:
                    assert task["status"] == "completed"
                    assert task["result"] == {"count": 5}
        finally:
            ToolContext.clear_context()

    async def test_execution_id_generated(self):
        """Test execution ID is generated."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{}'}]}

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)

                assert "execution_id" in parsed["data"]
                assert parsed["data"]["execution_id"].startswith("par-")
        finally:
            ToolContext.clear_context()

    async def test_duration_tracked(self):
        """Test total duration is tracked."""
        from agent.tools.mcp_tools import ToolContext

        ToolContext.set_context(None, "user1", "proj-1", "sess-1")
        try:
            with patch("agent.tools.parallel_executor.handle_query_files") as mock_query:
                mock_query.return_value = {"content": [{"type": "text", "text": '{}'}]}

                result = await execute_parallel([
                    {"type": "query_files", "description": "Q", "params": {}},
                ])

                text = result["content"][0]["text"]
                parsed = json.loads(text)

                assert "total_duration_ms" in parsed["data"]
                assert parsed["data"]["total_duration_ms"] >= 0
        finally:
            ToolContext.clear_context()
