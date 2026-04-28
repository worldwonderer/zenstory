"""
Token estimation utilities.

Provides unified token estimation for the agent system.
"""

from typing import Any

# Approximate characters per token (conservative for Chinese/English mix)
CHARS_PER_TOKEN = 4


def estimate_text_tokens(text: str) -> int:
    """
    Estimate token count for plain text.

    Uses simple character-based estimation.
    For more accurate results, use tiktoken.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """
    Estimate token count for a message dict.

    Handles various message formats including:
    - Simple string content
    - List of content blocks (text, thinking, tool_use, image)
    - Tool result messages

    Args:
        message: Message dict with role and content

    Returns:
        Estimated token count
    """
    chars = 0
    role = message.get("role", "")
    content = message.get("content", "")

    if role == "user":
        if isinstance(content, str):
            chars = len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    chars += len(block.get("text", ""))
        return max(1, chars // CHARS_PER_TOKEN)

    elif role == "assistant":
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        chars += len(block.get("text", ""))
                    elif block_type == "thinking":
                        chars += len(block.get("thinking", ""))
                    elif block_type == "tool_use":
                        name = block.get("name", "")
                        args = block.get("input", {})
                        chars += len(name) + len(str(args))
        elif isinstance(content, str):
            chars = len(content)
        return max(1, chars // CHARS_PER_TOKEN)

    elif role in ("tool_result", "custom"):
        if isinstance(content, str):
            chars = len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        chars += len(block.get("text", ""))
                    elif block.get("type") == "image":
                        chars += 4800  # ~1200 tokens per image
        return max(1, chars // CHARS_PER_TOKEN)

    # Default case
    if isinstance(content, str):
        return max(1, len(content) // CHARS_PER_TOKEN)

    return 0
