"""LangGraph-based chat assistant for Google MailPilot.

This package provides a conversational AI assistant with:
- Direct database access for email queries
- Engine client integration for mutations
- Human-in-the-loop for destructive operations
- Conversation persistence via PostgreSQL checkpointer
"""

from workspace_secretary.assistant.graph import create_assistant_graph, get_graph
from workspace_secretary.assistant.state import AssistantState
from workspace_secretary.assistant.context import AssistantContext
from workspace_secretary.assistant.starters import CONVERSATION_STARTERS, get_starters

__all__ = [
    "create_assistant_graph",
    "get_graph",
    "AssistantState",
    "AssistantContext",
    "CONVERSATION_STARTERS",
    "get_starters",
]
