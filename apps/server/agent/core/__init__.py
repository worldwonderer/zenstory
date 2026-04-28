"""
Core infrastructure for the agent module.

Provides:
- LLM client with sync/async/streaming support
- SSE event definitions
- Stream processor for file content streaming
- Message manager for chat history and system prompts
- Session loader for context and chat session loading
"""

from .events import EventType, StreamEvent
from .llm_client import LLMClient, get_llm_client
from .message_manager import MessageManager
from .session_loader import SessionData, SessionLoader
from .stream_processor import StreamProcessor, StreamResult, StreamState

__all__ = [
    "LLMClient",
    "get_llm_client",
    "EventType",
    "StreamEvent",
    "StreamProcessor",
    "StreamResult",
    "StreamState",
    "MessageManager",
    "SessionLoader",
    "SessionData",
]
