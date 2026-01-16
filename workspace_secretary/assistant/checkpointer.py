"""PostgreSQL checkpointer for LangGraph conversation persistence."""

import logging
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver

from workspace_secretary.config import PostgresConfig

logger = logging.getLogger(__name__)

_checkpointer: Optional[PostgresSaver] = None


def create_checkpointer(postgres_config: PostgresConfig) -> PostgresSaver:
    """Create and initialize a PostgreSQL checkpointer.

    Args:
        postgres_config: PostgreSQL connection configuration

    Returns:
        Configured PostgresSaver instance
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    # Build connection string
    conn_string = postgres_config.connection_string

    # Create checkpointer with connection pooling
    _checkpointer = PostgresSaver.from_conn_string(conn_string)

    # Initialize schema (creates tables if not exist)
    _checkpointer.setup()

    logger.info("PostgreSQL checkpointer initialized")
    return _checkpointer


def get_checkpointer() -> Optional[PostgresSaver]:
    """Get the global checkpointer instance.

    Returns:
        The checkpointer if initialized, None otherwise
    """
    return _checkpointer


def close_checkpointer() -> None:
    """Close the checkpointer connection."""
    global _checkpointer
    if _checkpointer is not None:
        # PostgresSaver handles connection cleanup internally
        _checkpointer = None
        logger.info("PostgreSQL checkpointer closed")
