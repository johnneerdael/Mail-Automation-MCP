"""Context container for assistant dependencies.

Provides database, engine client, and configuration access to tools.
"""

from dataclasses import dataclass
from typing import Any, Optional

from workspace_secretary.config import ServerConfig, UserIdentityConfig
from workspace_secretary.db.types import DatabaseInterface
from workspace_secretary.engine_client import EngineClient


@dataclass
class AssistantContext:
    """Runtime context for the assistant.

    Contains all dependencies needed by tools:
    - Database connection for read queries
    - Engine client for mutations
    - Configuration for user identity and settings
    """

    db: DatabaseInterface
    engine: EngineClient
    config: ServerConfig

    # Derived from config for convenience
    user_email: str
    user_name: str
    timezone: str

    @classmethod
    def from_config(
        cls,
        db: DatabaseInterface,
        engine: EngineClient,
        config: ServerConfig,
    ) -> "AssistantContext":
        """Create context from server configuration.

        Args:
            db: Database interface for queries
            engine: Engine client for mutations
            config: Server configuration

        Returns:
            AssistantContext with all fields populated
        """
        return cls(
            db=db,
            engine=engine,
            config=config,
            user_email=config.identity.email,
            user_name=config.identity.full_name or "",
            timezone=config.timezone,
        )

    @property
    def identity(self) -> UserIdentityConfig:
        """Get user identity configuration."""
        return self.config.identity

    @property
    def vip_senders(self) -> list[str]:
        """Get list of VIP sender emails."""
        return self.config.vip_senders

    @property
    def working_hours(self) -> dict[str, Any]:
        """Get working hours as dict."""
        return {
            "start": self.config.working_hours.start,
            "end": self.config.working_hours.end,
            "workdays": self.config.working_hours.workdays,
        }

    @property
    def embeddings_enabled(self) -> bool:
        """Check if semantic search is available."""
        return self.config.database.embeddings.enabled


# Global context instance (set during graph initialization)
_context: Optional[AssistantContext] = None


def set_context(ctx: AssistantContext) -> None:
    """Set the global assistant context."""
    global _context
    _context = ctx


def get_context() -> AssistantContext:
    """Get the global assistant context.

    Raises:
        RuntimeError: If context not initialized
    """
    if _context is None:
        raise RuntimeError(
            "AssistantContext not initialized. Call set_context() first."
        )
    return _context
