"""Conversation starters for the chat assistant.

Provides quick action buttons for common workflows.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationStarter:
    """A conversation starter / quick action.

    Attributes:
        id: Unique identifier
        label: Display label for button
        prompt: Message to send when clicked
        icon: Optional icon name (for UI)
        description: Optional longer description
    """

    id: str
    label: str
    prompt: str
    icon: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "label": self.label,
            "prompt": self.prompt,
            "icon": self.icon,
            "description": self.description,
        }


# Default conversation starters
CONVERSATION_STARTERS = [
    ConversationStarter(
        id="morning_brief",
        label="Morning Brief",
        prompt="Give me my morning briefing for today. Show me high-priority unread emails and my calendar for the day.",
        icon="sun",
        description="Get today's priority emails and calendar overview",
    ),
    ConversationStarter(
        id="cleanup_inbox",
        label="Cleanup Inbox",
        prompt="Help me clean up my inbox. Find newsletters, automated notifications, and low-priority emails that I can archive.",
        icon="trash",
        description="Find emails safe to archive or delete",
    ),
    ConversationStarter(
        id="prioritize_mailbox",
        label="Prioritize Mailbox",
        prompt="Identify high-priority unread emails that need my attention. Look for emails where I'm directly addressed, from VIP senders, or with urgent deadlines.",
        icon="flag",
        description="Find emails requiring immediate attention",
    ),
    ConversationStarter(
        id="draft_replies",
        label="Draft Replies",
        prompt="Find emails with questions directed at me that need a response, and help me draft replies for them.",
        icon="edit",
        description="Draft responses to pending questions",
    ),
    ConversationStarter(
        id="calendar_today",
        label="Today's Schedule",
        prompt="What's on my calendar for today? Show me my meetings and any conflicts.",
        icon="calendar",
        description="View today's meetings and schedule",
    ),
    ConversationStarter(
        id="unread_summary",
        label="Unread Summary",
        prompt="Summarize my unread emails. Group them by sender type (colleagues, external, automated) and urgency.",
        icon="mail",
        description="Get an overview of unread messages",
    ),
]


def get_starters() -> list[dict]:
    """Get all conversation starters as list of dicts.

    Returns:
        List of starter dictionaries for API response
    """
    return [s.to_dict() for s in CONVERSATION_STARTERS]


def get_starter_by_id(starter_id: str) -> Optional[ConversationStarter]:
    """Get a specific starter by ID.

    Args:
        starter_id: The starter's unique ID

    Returns:
        The starter if found, None otherwise
    """
    for starter in CONVERSATION_STARTERS:
        if starter.id == starter_id:
            return starter
    return None
