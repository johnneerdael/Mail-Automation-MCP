"""State schema for the LangGraph assistant.

Defines the TypedDict state that flows through the graph nodes.
"""

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    """State schema for the assistant graph.

    Attributes:
        messages: Conversation history with add_messages reducer
        user_id: Unique user identifier for session isolation
        user_email: User's email address for identity matching
        user_name: User's display name
        timezone: User's timezone (IANA format)
        working_hours: Working hours configuration dict
        selected_calendar_ids: List of calendar IDs to query
        pending_mutation: Tool call awaiting human approval
        continuation_state: State for batch tool continuation
        tool_error: Last tool error message if any
    """

    # Conversation messages with reducer for proper message handling
    messages: Annotated[list, add_messages]

    # User identity
    user_id: str
    user_email: str
    user_name: str

    # Scheduling configuration
    timezone: str
    working_hours: dict[str, Any]
    selected_calendar_ids: list[str]

    # Tool flow state
    pending_mutation: Optional[dict[str, Any]]
    continuation_state: Optional[str]
    tool_error: Optional[str]


def create_initial_state(
    user_id: str,
    user_email: str,
    user_name: str,
    timezone: str = "UTC",
    working_hours: Optional[dict[str, Any]] = None,
    selected_calendar_ids: Optional[list[str]] = None,
) -> AssistantState:
    """Create initial state for a new conversation.

    Args:
        user_id: Unique user identifier
        user_email: User's email address
        user_name: User's display name
        timezone: IANA timezone string
        working_hours: Working hours config dict
        selected_calendar_ids: Calendar IDs to query

    Returns:
        Initial AssistantState with empty messages
    """
    return AssistantState(
        messages=[],
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        timezone=timezone,
        working_hours=working_hours or {"start": "09:00", "end": "17:00"},
        selected_calendar_ids=selected_calendar_ids or ["primary"],
        pending_mutation=None,
        continuation_state=None,
        tool_error=None,
    )
