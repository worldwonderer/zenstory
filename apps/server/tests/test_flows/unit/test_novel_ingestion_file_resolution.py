from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import api.materials.helpers as materials_helpers
from flows.pipelines import novel_ingestion_v3_flow as flow_mod


class _FakeResponse:
    def __init__(self, content: bytes):
        self._content = content

    def read(self):
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestEnsureFileLocal:
    def test_returns_existing_path_directly(self, tmp_path: Path):
        file_path = tmp_path / "novel.txt"
        file_path.write_text("hello", encoding="utf-8")

        out = flow_mod._ensure_file_local(str(file_path), user_id="u1", logger=MagicMock())

        assert out == str(file_path)

    def test_raises_when_missing_api_server_url(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "missing.txt"
        monkeypatch.delenv("API_SERVER_INTERNAL_URL", raising=False)
        monkeypatch.delenv("MATERIAL_INTERNAL_TOKEN", raising=False)

        with pytest.raises(FileNotFoundError, match="API_SERVER_INTERNAL_URL"):
            flow_mod._ensure_file_local(str(target), user_id="u1", logger=MagicMock())

    def test_raises_when_missing_internal_token(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "missing.txt"
        monkeypatch.setenv("API_SERVER_INTERNAL_URL", "http://api.internal")
        monkeypatch.delenv("MATERIAL_INTERNAL_TOKEN", raising=False)

        with pytest.raises(FileNotFoundError, match="MATERIAL_INTERNAL_TOKEN"):
            flow_mod._ensure_file_local(str(target), user_id="u1", logger=MagicMock())

    def test_downloads_file_when_not_local(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "uploads" / "novel.txt"
        logger = MagicMock()

        monkeypatch.setenv("API_SERVER_INTERNAL_URL", "http://api.internal")
        monkeypatch.setenv("MATERIAL_INTERNAL_TOKEN", "token-123")
        monkeypatch.setattr(
            flow_mod.urllib.request,
            "urlopen",
            lambda _req, timeout=30: _FakeResponse(b"downloaded-content"),
        )

        out = flow_mod._ensure_file_local(str(target), user_id="user-9", logger=logger)

        assert out == str(target)
        assert target.exists()
        assert target.read_bytes() == b"downloaded-content"
        assert logger.info.call_count >= 1


@pytest.mark.asyncio
async def test_start_flow_deployment_persists_flow_run_id(monkeypatch):
    class _FlowRun:
        id = "flow-run-123"

    async def _run_deployment(**kwargs):
        return _FlowRun()

    class _Job:
        def __init__(self):
            self.correlation_id = None
            self.updated_at = None
            self.stage_progress = "{}"

        def update_stage_progress(self, stage: str, status: str, **kwargs):
            self.stage_progress = f"{stage}:{status}:{kwargs.get('flow_run_id')}"

    class _QueryResult:
        def __init__(self, job):
            self._job = job

        def first(self):
            return self._job

    class _Session:
        def __init__(self, job):
            self.job = job
            self.commits = 0

        def exec(self, _stmt):
            return _QueryResult(self.job)

        def add(self, _obj):
            return None

        def commit(self):
            self.commits += 1

        def close(self):
            return None

    job = _Job()
    monkeypatch.setattr(materials_helpers, "create_session", lambda: _Session(job))
    monkeypatch.setitem(
        __import__("sys").modules,
        "prefect.deployments",
        SimpleNamespace(run_deployment=_run_deployment),
    )

    flow_run_id = await materials_helpers._start_flow_deployment(
        file_path="/tmp/test.txt",
        novel_title="Novel",
        author="Author",
        user_id="user-1",
        novel_id=1,
    )

    assert str(flow_run_id) == "flow-run-123"
    assert job.correlation_id == "flow-run-123"
