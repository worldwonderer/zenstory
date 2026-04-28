"""
Agent module for AI-powered novel writing assistance.

This module provides:
- Intent classification and routing
- Context assembly with priority management
- Various writing actions (continue, rewrite, expand, etc.)
- Consistency checking
- Streaming response support
"""

from .service import AgentService, get_agent_service

__all__ = ["AgentService", "get_agent_service"]
