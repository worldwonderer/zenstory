"""Prompt/tool alignment regression tests.

These tests ensure that the system prompt does not instruct the model to call
tools that are not available in the Anthropic tool registry.
"""

import pytest

from agent.prompts.base import get_base_prompt
from agent.prompts.novel import NOVEL_PROMPT_CONFIG


@pytest.mark.unit
def test_base_prompt_does_not_suggest_removed_tools():
    prompt = get_base_prompt(
        project_id="proj-1",
        folder_ids={
            "draft": "draft-folder",
            "outline": "outline-folder",
            "character": "character-folder",
            "lore": "lore-folder",
            "material": "material-folder",
        },
        config=NOVEL_PROMPT_CONFIG,
    )

    # We allow a plain-language note that tools don't exist, but the prompt
    # must not present them as callables (e.g. backticks, examples, tool list).
    assert "`update_file`" not in prompt
    assert "`read_file`" not in prompt
    assert "\n- update_file" not in prompt
    assert "update_file(" not in prompt
    assert "read_file(" not in prompt

