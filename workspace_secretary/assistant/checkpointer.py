"""PostgreSQL checkpointer for LangGraph conversation persistence."""

import logging
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from workspace_secretary.config import PostgresConfig

logger = logging.getLogger(__name__)

_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_cm = None


async def create_checkpointer(postgres_config: PostgresConfig) -> AsyncPostgresSaver:
    global _checkpointer, _checkpointer_cm

    if _checkpointer is not None:
        return _checkpointer

    conn_string = postgres_config.connection_string
    
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(conn_string)
    _checkpointer = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()

    logger.info("PostgreSQL async checkpointer initialized")
    return _checkpointer


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
    _checkpointer = None
    logger.info("PostgreSQL checkpointer closed")
