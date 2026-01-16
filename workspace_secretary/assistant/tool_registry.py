"""Tool registry with classification metadata.

Categorizes tools as read-only vs mutation for HITL routing.
"""

from typing import Callable, Literal, NamedTuple

from workspace_secretary.assistant.tools_read import READ_ONLY_TOOLS
from workspace_secretary.assistant.tools_mutation import MUTATION_TOOLS


class ToolInfo(NamedTuple):
    """Metadata about a tool."""

    name: str
    category: Literal["readonly", "mutation", "staging"]
    description: str


# Tool classification registry
TOOL_REGISTRY: dict[str, ToolInfo] = {
    # Read-only tools (safe, no HITL needed)
    "list_folders": ToolInfo("list_folders", "readonly", "List email folders"),
    "search_emails": ToolInfo("search_emails", "readonly", "Search emails with FTS"),
    "get_email_details": ToolInfo(
        "get_email_details", "readonly", "Get full email content"
    ),
    "get_email_thread": ToolInfo(
        "get_email_thread", "readonly", "Get conversation thread"
    ),
    "get_unread_messages": ToolInfo(
        "get_unread_messages", "readonly", "List unread emails"
    ),
    "get_daily_briefing": ToolInfo(
        "get_daily_briefing", "readonly", "Daily briefing summary"
    ),
    "list_calendar_events": ToolInfo(
        "list_calendar_events", "readonly", "List calendar events"
    ),
    "get_calendar_availability": ToolInfo(
        "get_calendar_availability", "readonly", "Check free/busy"
    ),
    # Safe staging tools (create drafts, no external mutation)
    "create_draft_reply": ToolInfo(
        "create_draft_reply", "staging", "Create draft reply"
    ),
    # Mutation tools (require HITL approval)
    "mark_as_read": ToolInfo("mark_as_read", "mutation", "Mark email as read"),
    "mark_as_unread": ToolInfo("mark_as_unread", "mutation", "Mark email as unread"),
    "move_email": ToolInfo("move_email", "mutation", "Move email to folder"),
    "modify_gmail_labels": ToolInfo(
        "modify_gmail_labels", "mutation", "Add/remove labels"
    ),
    "send_email": ToolInfo("send_email", "mutation", "Send email"),
    "create_calendar_event": ToolInfo(
        "create_calendar_event", "mutation", "Create calendar event"
    ),
    "respond_to_meeting": ToolInfo(
        "respond_to_meeting", "mutation", "Respond to meeting invite"
    ),
    "execute_clean_batch": ToolInfo(
        "execute_clean_batch", "mutation", "Execute batch cleanup"
    ),
}


def is_mutation_tool(tool_name: str) -> bool:
    """Check if a tool is a mutation tool requiring HITL."""
    info = TOOL_REGISTRY.get(tool_name)
    return info is not None and info.category == "mutation"


def is_readonly_tool(tool_name: str) -> bool:
    """Check if a tool is read-only (safe to execute)."""
    info = TOOL_REGISTRY.get(tool_name)
    return info is not None and info.category in ("readonly", "staging")


def get_tool_category(tool_name: str) -> str:
    """Get the category of a tool."""
    info = TOOL_REGISTRY.get(tool_name)
    return info.category if info else "unknown"


def get_all_tools() -> list[Callable]:
    """Get all available tools."""
    return READ_ONLY_TOOLS + MUTATION_TOOLS


def get_readonly_tools() -> list[Callable]:
    """Get read-only tools only."""
    return READ_ONLY_TOOLS


def get_mutation_tools() -> list[Callable]:
    """Get mutation tools only."""
    return MUTATION_TOOLS


def get_tool_names_by_category(category: str) -> list[str]:
    """Get tool names for a given category."""
    return [name for name, info in TOOL_REGISTRY.items() if info.category == category]
