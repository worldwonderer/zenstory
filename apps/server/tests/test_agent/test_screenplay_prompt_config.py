"""Tests for screenplay prompt formatting requirements."""

import pytest

from agent.prompts.screenplay import SCREENPLAY_PROMPT_CONFIG


@pytest.mark.unit
class TestScreenplayPromptFormatting:
    """Ensure screenplay prompt enforces industry-friendly dual-format output."""

    def test_content_structure_requires_dual_format_delivery(self):
        content_structure = SCREENPLAY_PROMPT_CONFIG["content_structure"]

        assert "双轨交付" in content_structure
        assert "文学剧本版" in content_structure
        assert "拍摄执行版" in content_structure
        assert "输出顺序（必须）" in content_structure

    def test_writing_guidelines_define_default_and_override_dual_format_behavior(self):
        writing_guidelines = SCREENPLAY_PROMPT_CONFIG["writing_guidelines"]

        assert "双轨格式执行规则" in writing_guidelines
        assert "默认输出双轨" in writing_guidelines
        assert "当用户只要其中一种格式时，仅输出指定格式" in writing_guidelines

    def test_content_structure_requires_core_outline_autocreation(self):
        content_structure = SCREENPLAY_PROMPT_CONFIG["content_structure"]

        assert "核心大纲" in content_structure
        assert "metadata_filter={\"outline_kind\":\"core\"}" in content_structure
        assert "parent_id='{outline}'" in content_structure
        # Ensure the prompt instructs stable ordering so the core outline appears first.
        assert "order=0" in content_structure
        # Template fields should exist so the model can output structured plain text.
        assert "【一句话梗概】" in content_structure
