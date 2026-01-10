# Architecture v4.2.4

This document describes the sync engine architecture including parallel folder sync, IMAP connection pooling, and the IDLE threading model.

## Sync Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         asyncio event loop                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  sync_loop()              idle_monitor()           embeddings_loop()     │
│  ───────────              ─────────────            ─────────────────     │
│  1. Initial parallel      Manages thread           Background vector     │
│     sync (all folders)    lifecycle only           generation            │
│  2. Sleep 30 min                                                         │
│  3. Catch-up sync         ┌─────────────┐                                │
│  4. Repeat                │ IDLE Thread │                                │
│         │                 │ ─────────── │                                │
│         │                 │ select_folder                                │
│         ▼                 │ idle_start   │                               │
│  ┌─────────────────┐      │ idle_check   │──► loop.call_soon_threadsafe  │
│  │ ThreadPoolExecutor     │ idle_done    │         │                     │
│  │ (5 workers)     │      └──────────────┘         ▼                     │
│  │                 │                         debounced_sync()            │
│  │ ┌─────────────┐ │                               │                     │
│  │ │ IMAP Pool   │ │                               ▼                     │
│  │ │ Queue(5)    │ │◄────────────────────── sync_emails_parallel()       │
│  │ └─────────────┘ │                                                     │
│  └─────────────────┘                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Connection Architecture

| Connection | Purpose | Thread | Lifecycle |
|------------|---------|--------|-----------|
| `idle_client` | IMAP IDLE for INBOX push | Dedicated `idle-worker` thread | Startup → shutdown |
| Connection Pool (1-5) | Parallel folder sync | `ThreadPoolExecutor` workers | On-demand, pooled |

## Sync Strategy

### Phase 1: Initial Sync (Startup)

All configured folders sync in parallel using the connection pool:

```
Folders: [INBOX, Sent, Drafts, [Gmail]/All Mail]
Pool:    [conn1, conn2, conn3, conn4, conn5]

conn1 → INBOX
conn2 → Sent
conn3 → Drafts
conn4 → [Gmail]/All Mail
conn5 → (idle in pool)
```

### Phase 2: Real-time Updates (IDLE)

INBOX monitored via IMAP IDLE on dedicated thread:
- `EXISTS` → new email arrived
- `EXPUNGE` → email deleted
- Triggers `debounced_sync()` via `loop.call_soon_threadsafe()`

### Phase 3: Catch-up Sync (Periodic)

Every 30 minutes (configurable), parallel sync runs again to:
- Sync non-INBOX folders (Sent, Drafts, labels)
- Catch missed IDLE notifications (connection drops)
- Update flags via CONDSTORE/HIGHESTMODSEQ

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MAX_SYNC_CONNECTIONS` | 5 | Size of IMAP connection pool |
| `SYNC_CATCHUP_INTERVAL` | 1800 | Catch-up sync interval in seconds (30 min) |

## Why This Architecture?

### Problem: IMAP Blocking Calls

IMAP operations (`select_folder`, `idle_check`, `fetch`) are blocking. Running them on the asyncio event loop freezes all async tasks.

### Solution: Dedicated Threads

1. **IDLE Thread**: Runs entire IDLE loop (`select_folder` → `idle_start` → `idle_check` → `idle_done`) on a dedicated thread. Communicates back via `loop.call_soon_threadsafe()`.

2. **Sync Thread Pool**: `ThreadPoolExecutor` with pooled IMAP connections. Each folder sync runs in its own worker thread. `asyncio.gather()` coordinates parallel execution.

### Result

- Event loop never blocks
- Up to 5 folders sync simultaneously
- IDLE provides instant INBOX updates
- Catch-up sync handles edge cases

## Gmail Connection Limits

Gmail allows up to 15 simultaneous IMAP connections per account. This architecture uses:
- 1 connection for IDLE
- Up to 5 connections for sync pool
- Total: 6 connections (well under limit)
