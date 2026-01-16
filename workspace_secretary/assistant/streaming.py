"""SSE event streaming utilities for the LangGraph assistant."""

import json
from typing import Any, AsyncIterator


async def format_sse_events(
    events: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """Format LangGraph events as Server-Sent Events.

    Transforms LangGraph astream_events output into SSE format
    suitable for browser EventSource consumption.

    Args:
        events: Async iterator of LangGraph events

    Yields:
        SSE formatted strings
    """
    async for event in events:
        event_type = event.get("event", "")

        # Handle different event types
        if event_type == "on_chat_model_stream":
            # Streaming token from LLM
            chunk = event.get("data", {}).get("chunk", {})
            content = chunk.get("content", "")
            if content:
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

        elif event_type == "on_tool_start":
            # Tool execution starting
            tool_name = event.get("name", "unknown")
            yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"

        elif event_type == "on_tool_end":
            # Tool execution completed
            tool_name = event.get("name", "unknown")
            output = event.get("data", {}).get("output", "")
            yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'output': str(output)[:500]})}\n\n"

        elif event_type == "on_chain_end":
            # Chain/graph completed
            if event.get("name") == "LangGraph":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"


def format_error_sse(error: str) -> str:
    """Format an error as SSE event.

    Args:
        error: Error message

    Returns:
        SSE formatted error string
    """
    return f"data: {json.dumps({'type': 'error', 'message': error})}\n\n"


def format_interrupt_sse(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Format a HITL interrupt as SSE event.

    Args:
        tool_name: Name of the mutation tool
        tool_args: Arguments for the tool

    Returns:
        SSE formatted interrupt request
    """
    return f"data: {json.dumps({'type': 'interrupt', 'tool': tool_name, 'args': tool_args})}\n\n"


def extract_final_response(state: dict) -> str:
    """Extract the final assistant response from state.

    Args:
        state: Final graph state after execution

    Returns:
        The last assistant message content
    """
    messages = state.get("messages", [])

    # Find the last AI message
    for msg in reversed(messages):
        # Handle different message formats
        if hasattr(msg, "type") and msg.type == "ai":
            return msg.content
        elif isinstance(msg, dict) and msg.get("type") == "ai":
            return msg.get("content", "")
        elif hasattr(msg, "role") and msg.role == "assistant":
            return msg.content

    return "No response generated."
