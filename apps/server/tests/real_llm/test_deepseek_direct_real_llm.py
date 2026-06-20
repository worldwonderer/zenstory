import pytest


@pytest.mark.integration
@pytest.mark.real_llm
async def test_deepseek_direct_chat_completions_smoke(require_deepseek_key):
    """Minimal real-provider smoke for the shared DeepSeek client wiring."""
    from agent.core.deepseek_client import DEEPSEEK_CHAT_MODEL, get_deepseek_client

    client = get_deepseek_client()
    response = await client.chat.completions.create(
        model=DEEPSEEK_CHAT_MODEL,
        messages=[
            {"role": "system", "content": "Return exactly one short sentence."},
            {"role": "user", "content": "Say migration smoke passed."},
        ],
        temperature=0.0,
        # deepseek-v4-flash is a reasoning model: reasoning_tokens count against the
        # completion budget, so a tiny max_tokens (e.g. 32) is fully consumed by reasoning
        # and leaves message.content empty. Give enough room for reasoning + the sentence.
        max_tokens=512,
    )

    content = response.choices[0].message.content or ""
    assert response.model
    assert content.strip()
