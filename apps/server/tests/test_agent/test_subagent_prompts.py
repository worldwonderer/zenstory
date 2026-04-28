"""Tests for agent subagent prompts consistency."""

import pytest

from agent.prompts.subagents import QUALITY_REVIEWER_PROMPT, WRITER_PROMPT
from config.agent_runtime import AGENT_AUTO_REVIEW_THRESHOLD_CHARS


@pytest.mark.unit
class TestWriterPromptConsistency:
    """Ensure writer prompt stays aligned with runtime workflow config."""

    def test_writer_handoff_target_uses_quality_reviewer(self):
        """Writer prompt should hand off to quality_reviewer, not reviewer."""
        assert 'target_agent: "quality_reviewer"' in WRITER_PROMPT
        assert 'target_agent: "reviewer"' not in WRITER_PROMPT

    def test_writer_review_threshold_uses_runtime_constant(self):
        """Writer prompt threshold text should use centralized runtime threshold."""
        assert f"超过 **{AGENT_AUTO_REVIEW_THRESHOLD_CHARS}字**" in WRITER_PROMPT
        assert f"少于 {AGENT_AUTO_REVIEW_THRESHOLD_CHARS} 字" in WRITER_PROMPT
        assert f"写完 {AGENT_AUTO_REVIEW_THRESHOLD_CHARS} 字以上内容后直接结束" in WRITER_PROMPT


@pytest.mark.unit
class TestQualityReviewerPromptConsistency:
    """Ensure reviewer prompt stays aligned with restricted tool permissions."""

    def test_quality_reviewer_prompt_does_not_require_direct_edit_file(self):
        assert "必要时直接使用 `edit_file` 修正" not in QUALITY_REVIEWER_PROMPT
        assert "错别字、标点、格式问题也需交接给 writer 修正" in QUALITY_REVIEWER_PROMPT
        assert "除非是小的格式/标点修正" not in QUALITY_REVIEWER_PROMPT
        assert "### 已自动修正" not in QUALITY_REVIEWER_PROMPT
