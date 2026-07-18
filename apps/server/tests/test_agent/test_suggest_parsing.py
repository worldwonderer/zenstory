"""Regression tests for suggestion JSON parsing.

The prompt's example invites a bare top-level array, but the parser only ever
read ``data.get("suggestions")`` — a list has no ``.get``, so valid array output
was silently discarded and canned fallbacks were used instead.
"""

from agent.suggest_service import SuggestService


def test_coerce_suggestions_accepts_bare_array():
    assert SuggestService._coerce_suggestions(["a", "b"]) == ["a", "b"]


def test_coerce_suggestions_accepts_object():
    assert SuggestService._coerce_suggestions({"suggestions": ["x"]}) == ["x"]


def test_coerce_suggestions_object_missing_key():
    assert SuggestService._coerce_suggestions({"other": 1}) == []


def test_coerce_suggestions_ignores_non_json_types():
    assert SuggestService._coerce_suggestions("nope") == []
    assert SuggestService._coerce_suggestions(None) == []


def test_extract_json_blob_prefers_object():
    assert SuggestService._extract_json_blob('noise {"suggestions": []} tail') == '{"suggestions": []}'


def test_extract_json_blob_falls_back_to_array():
    assert SuggestService._extract_json_blob('prefix ["a", "b"] suffix') == '["a", "b"]'


def test_extract_json_blob_none_when_absent():
    assert SuggestService._extract_json_blob("just prose, no json") is None


def test_parse_json_suggestions_from_bare_array():
    svc = SuggestService()
    parsed = svc._parse_json_suggestions('["写一段对话", "补充环境描写"]')
    assert parsed == ["写一段对话", "补充环境描写"]
