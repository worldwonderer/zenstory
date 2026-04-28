from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

from flows.pipelines.helpers.progress_publisher import ProgressPublisher


class TestProgressPublisher:
    def test_no_correlation_id_disables_client(self):
        publisher = ProgressPublisher(correlation_id=None, logger=MagicMock())
        assert publisher._client is None

        # should not raise
        publisher.publish("flow_started", progress=0)

    def test_publish_sends_json_payload_to_expected_channel(self, monkeypatch):
        fake_client = MagicMock()
        monkeypatch.setattr(
            ProgressPublisher,
            "_create_redis_client",
            lambda self: fake_client,
        )

        publisher = ProgressPublisher(correlation_id="cid-123", logger=MagicMock())
        publisher.publish("stage1_completed", progress=50, message="ok")

        fake_client.publish.assert_called_once()
        channel, payload = fake_client.publish.call_args.args
        parsed = json.loads(payload)

        assert channel == "ingestion:cid-123"
        assert parsed["type"] == "stage1_completed"
        assert parsed["progress"] == 50
        assert parsed["message"] == "ok"
        assert "timestamp" in parsed

    def test_publish_with_unavailable_client_only_warns(self, monkeypatch):
        logger = MagicMock()
        monkeypatch.setattr(ProgressPublisher, "_create_redis_client", lambda self: None)

        publisher = ProgressPublisher(correlation_id="cid-123", logger=logger)
        publisher.publish("stage2_started", progress=60)

        assert logger.warning.call_count >= 1

    def test_publish_completion_includes_summary(self, monkeypatch):
        publisher = ProgressPublisher(correlation_id=None, logger=MagicMock())
        publisher.publish = MagicMock()
        monkeypatch.setattr(
            publisher,
            "_build_novel_summary",
            lambda novel_id, chapters_count: {
                "id": novel_id,
                "chapters_count": chapters_count,
            },
        )

        publisher.publish_completion(
            novel_id=7,
            chapter_ids=[1, 2, 3],
            result={"elapsed_ms": 88},
        )

        publisher.publish.assert_called_once()
        args, kwargs = publisher.publish.call_args
        assert args[0] == "completed"
        assert kwargs["novel_summary"] == {"id": 7, "chapters_count": 3}
        assert kwargs["progress"] == 100

    def test_publish_completion_allows_missing_summary(self, monkeypatch):
        publisher = ProgressPublisher(correlation_id=None, logger=MagicMock())
        publisher.publish = MagicMock()
        monkeypatch.setattr(publisher, "_build_novel_summary", lambda _novel_id, _chapters_count: None)

        publisher.publish_completion(
            novel_id=9,
            chapter_ids=[10],
            result={"elapsed_ms": 12},
        )

        args, kwargs = publisher.publish.call_args
        assert args[0] == "completed"
        assert kwargs["novel_summary"] is None

    def test_build_novel_summary_returns_none_on_query_error(self, monkeypatch):
        logger = MagicMock()
        publisher = ProgressPublisher(correlation_id=None, logger=logger)

        import flows.database_session as db_session_mod

        @contextmanager
        def _broken_session():
            class _Broken:
                def exec(self, _stmt):
                    raise RuntimeError("db unavailable")

            yield _Broken()

        monkeypatch.setattr(db_session_mod, "get_prefect_db_session", _broken_session)

        summary = publisher._build_novel_summary(novel_id=1, chapters_count=2)
        assert summary is None
        logger.warning.assert_called_once()
