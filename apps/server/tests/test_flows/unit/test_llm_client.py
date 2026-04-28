from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from flows.utils.clients import llm as llm_mod
from flows.utils.helpers.exceptions import LLMAPIError


class TestLLMClientHelpers:
    def _new_client(self):
        return llm_mod.GeminiClient.__new__(llm_mod.GeminiClient)

    def test_extract_json_from_plain_json(self):
        client = self._new_client()
        response = llm_mod.LLMResponse(content='{"a": 1}', usage={}, model="m", finish_reason="stop")
        assert client.extract_json_from_response(response) == {"a": 1}

    def test_extract_json_from_markdown_codeblock(self):
        client = self._new_client()
        content = """Here is result:\n```json\n{\"a\": 2, \"b\": 3}\n```"""
        response = llm_mod.LLMResponse(content=content, usage={}, model="m", finish_reason="stop")
        assert client.extract_json_from_response(response) == {"a": 2, "b": 3}

    def test_extract_json_from_embedded_object(self):
        client = self._new_client()
        response = llm_mod.LLMResponse(content="prefix {\"ok\": true} suffix", usage={}, model="m", finish_reason="stop")
        assert client.extract_json_from_response(response) == {"ok": True}

    def test_extract_json_raises_when_no_valid_json(self):
        client = self._new_client()
        response = llm_mod.LLMResponse(content="not a json", usage={}, model="m", finish_reason="stop")
        with pytest.raises(LLMAPIError):
            client.extract_json_from_response(response)

    def test_validate_response_format_missing_field_returns_false(self, monkeypatch):
        client = self._new_client()
        logger = MagicMock()
        monkeypatch.setattr(llm_mod, "get_logger", lambda _name: logger)

        response = llm_mod.LLMResponse(content='{"a": 1}', usage={}, model="m", finish_reason="stop")
        ok = client.validate_response_format(response, ["a", "b"])

        assert ok is False
        assert logger.warning.call_count >= 1

    def test_validate_response_format_invalid_json_logs_error(self, monkeypatch):
        client = self._new_client()
        logger = MagicMock()
        log_error = MagicMock()
        monkeypatch.setattr(llm_mod, "get_logger", lambda _name: logger)
        monkeypatch.setattr(llm_mod, "log_error_with_context", log_error)

        response = llm_mod.LLMResponse(content="invalid", usage={}, model="m", finish_reason="stop")
        ok = client.validate_response_format(response, ["a"])

        assert ok is False
        assert log_error.call_count == 1
