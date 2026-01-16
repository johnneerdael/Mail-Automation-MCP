# LangGraph Chat Assistant Implementation Plan

## 1) Architecture Overview

```
┌────────────────────────────┐
│        Web Client          │
│  chat UI + starters UI     │
└──────────────┬─────────────┘
               │ HTTP/SSE
               ▼
┌────────────────────────────┐
│ FastAPI /api/chat endpoints│
│  - sync + stream           │
│  - starters endpoint       │
└──────────────┬─────────────┘
               │ graph.invoke / astream_events
               ▼
┌────────────────────────────────────────────────────────────┐
│ LangGraph StateGraph (checkpointer=PostgresSaver)           │
│                                                            │
│  START                                                     │
│    │                                                       │
│    ▼                                                       │
│  build_context ──► llm_reason ──tools_condition──┐          │
│                                  │                │         │
│                                  ▼                ▼         │
│                           readonly_tools     mutation_tools │
│                                  │                │         │
│                                  └───► llm_reason │         │
│                                                   │         │
│                                   interrupt_before=["mutation_tools"]
│                                                   │         │
│                                                   ▼         │
│                                            human_confirm    │
│                                                   │         │
│                                                   ▼         │
│                                               tool_exec     │
│                                                   │         │
│                                                   ▼         │
│                                                llm_reason   │
│                                                   │         │
│                                                   ▼         │
│                                                 __end__     │
└────────────────────────────────────────────────────────────┘
```

## 2) File Structure

```
workspace_secretary/assistant/
  __init__.py
  state.py                  # TypedDict state + reducers
  context.py                # AssistantContext for injected deps
  tools_read.py             # @tool read-only + safe staging tools
  tools_mutation.py         # @tool mutation tools (HITL)
  tool_registry.py          # classification metadata
  graph.py                  # StateGraph builder + compile()
  checkpointer.py           # PostgresSaver factory + setup
  starters.py               # conversation starters catalog
  streaming.py              # SSE event shaping for graph events
```

## 3) State Schema (TypedDict)

```python
from typing import Optional, TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AssistantState(TypedDict):
    messages: List[BaseMessage]  # reducer=add_messages

    # identity/session
    user_id: str
    user_email: str
    user_name: str

    # config & scheduling
    timezone: str
    working_hours: Dict[str, Any]       # from WorkingHoursConfig
    selected_calendar_ids: List[str]

    # tool flow state
    pending_mutation: Optional[Dict[str, Any]]
    continuation_state: Optional[str]   # batch tool continuation
    tool_error: Optional[str]

    # context cache (optional)
    last_tool_result: Optional[Dict[str, Any]]
    last_prompt: Optional[str]
```

**Reducer configuration**:
```python
state = {"messages": add_messages}
```

## 4) Tool Classification

### Read-only tools (DB reads / safe)
- `list_folders`
- `search_emails`
- `gmail_search`
- `get_email_details`
- `get_email_thread`
- `get_unread_messages`
- `get_daily_briefing`
- `list_calendar_events`
- `get_calendar_availability`
- `semantic_search_emails`
- `semantic_search_filtered`
- `find_related_emails`

### Safe staging tools (no external mutations)
- `create_draft_reply` (drafts only, no send)
- `create_task` (writes tasks.md)

### Mutation tools (HITL required per AGENTS.md)
- `mark_as_read`
- `mark_as_unread`
- `move_email`
- `modify_gmail_labels`
- `process_email`
- `send_email`
- `create_calendar_event`
- `respond_to_meeting`
- `execute_clean_batch`

### Batch tools (read-only but time-boxed)
- `quick_clean_inbox`
- `triage_priority_emails`
- `triage_remaining_emails`

## 5) Node Implementations

1. **build_context**
   - Inject `db`, `engine`, `config`, `user_identity` into `AssistantContext`.
   - Load `selected_calendar_ids` from DB for the user.
   - Set timezone + working hours.

2. **llm_reason**
   - Call LLM with `messages` and tool definitions.
   - Append model response to state.
   - Uses existing config in `workspace_secretary/config.py`.

3. **readonly_tools (ToolNode)**
   - Executes read-only + safe staging tools.
   - Uses `InjectedState` to access db/engine/config/user.

4. **mutation_tools (ToolNode)**
   - Executes mutation tools only after human approval.
   - Uses `interrupt_before=["mutation_tools"]` to pause.

5. **human_confirm**
   - Presents pending mutation tool + args to UI.
   - Stores confirmation payload in state for resume.

6. **tool_exec**
   - Executes approved mutation tool after resume.
   - Writes tool result into state, then loops back to `llm_reason`.

## 6) Edge Routing Logic

- `llm_reason` → `tools_condition`:
  - If last AI message has tool calls → route to tool node.
  - Otherwise → `__end__`.

- Tool routing:
  - If any tool call is mutation → `mutation_tools`.
  - Else → `readonly_tools`.

- HITL:
  - `interrupt_before=["mutation_tools"]` in `graph.compile`.
  - On interrupt, UI must ask for approval and resume with `Command(resume=payload)`.

- Batch tools:
  - `quick_clean_inbox` and triage tools must auto-loop internally until `has_more=false` before returning to LLM.

## 7) Conversation Starters API

### Endpoint
`GET /api/chat/starters`

### Response
```json
[
  {"id": "morning_brief", "label": "Morning Brief", "prompt": "Run my morning briefing for today."},
  {"id": "cleanup_inbox", "label": "Cleanup Inbox", "prompt": "Find cleanup candidates in my inbox."},
  {"id": "prioritize_mailbox", "label": "Prioritize Mailbox", "prompt": "Identify high-priority unread emails."},
  {"id": "draft_reply", "label": "Draft Reply", "prompt": "Draft replies for high-priority messages."}
]
```

### UI
- Buttons trigger POST `/api/chat` with the starter `prompt`.

## 8) Web Route Integration

### Replace in `workspace_secretary/web/routes/chat.py`
- Remove `LLMClient` usage.
- Initialize LangGraph from `assistant.graph`.
- Use `thread_id=session.user_id` for checkpointer.
- For streaming: `graph.astream_events()` and forward SSE events.

### Pseudocode (sync)
```python
graph = get_graph()  # compiled with PostgresSaver
config = {"configurable": {"thread_id": session.user_id}}

result = graph.invoke(
    {"messages": [("user", message)], "user_id": session.user_id, ...},
    config=config,
)
return {"response": extract_final_text(result["messages"])}
```

### Pseudocode (stream)
```python
async for event in graph.astream_events(
    {"messages": [("user", message)], ...}, config=config
):
    yield format_sse(event)
```

## 9) Implementation Tasks (ordered)

| # | Task | Dependencies | Est. |
|---|------|--------------|------|
| 1 | Create `workspace_secretary/assistant/` package scaffold | - | 15m |
| 2 | Implement `state.py` and `context.py` | 1 | 30m |
| 3 | Build `tools_read.py` using direct DB queries and `@tool` | 2 | 2h |
| 4 | Build `tools_mutation.py` using `EngineClient` | 2 | 1h |
| 5 | Add `tool_registry.py` with classification metadata | 3, 4 | 30m |
| 6 | Implement `graph.py` with `StateGraph`, `ToolNode`, `tools_condition` | 5 | 2h |
| 7 | Implement `checkpointer.py` with `PostgresSaver.setup()` | 1 | 30m |
| 8 | Implement `streaming.py` for SSE event shaping | 6 | 1h |
| 9 | Add `starters.py` + `GET /api/chat/starters` route | 1 | 30m |
| 10 | Replace chat endpoints in `web/routes/chat.py` | 6, 7, 8 | 1h |
| 11 | Update UI to call starters endpoint | 9, 10 | 30m |
| 12 | Add tests for HITL gating, routing, persistence, streaming | All | 2h |

**Total estimated time: ~12 hours**

## 10) Testing Strategy

### Unit Tests
- Tool classification + routing logic
- Mutation tool interrupts with `interrupt_before`
- State reducer behavior (add_messages)

### Integration Tests
- Read-only tool flow returns correct results
- HITL: simulate resume with `Command(resume=approval_payload)`
- Batch tool continuation loop

### E2E Tests
- Persistence: verify checkpoints using `PostgresSaver.list()`
- Streaming: ensure SSE emits tokens + tool activity markers
- Conversation starters trigger correct prompts

### Manual Testing
- Test each conversation starter
- Verify mutation approval flow in UI
- Test conversation persistence across page reloads

---

## Dependencies to Add

```toml
# pyproject.toml
langgraph = "^0.2"
langchain-core = "^0.3"
langchain-anthropic = "^0.3"  # or langchain-openai
langgraph-checkpoint-postgres = "^2.0"
```

---

**Created**: 2025-01-16  
**Status**: Ready for implementation
