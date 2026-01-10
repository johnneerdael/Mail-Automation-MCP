# Architecture v4.2.3

This document describes the **read/write split architecture** along with the IDLE threading refactor introduced in v4.2.3. The changes aim to fix blocking event loops and enhance the overall sync engine performance for Gmail Secretary MCP.

## Overview

The Gmail Secretary MCP utilizes advanced threading mechanisms for IMAP IDLE operations to prevent blocking the asyncio event loop. All IDLE-related operations were delegated to a separate dedicated worker thread.

```
┌───────────────────────────────────────────────────────────────────┐
│                    asyncio event loop                             │
├───────────────────────────────────────────────────────────────────┤
│ sync_loop()        │ idle_monitor()    │ embeddings_loop()         │
│ ───────────        │ ───────────       │ _loop()                   │
│ while running:     │ while running:    │                           │
│   sync_emails()    │   idle_worker()   │                           │
│   await sleep(300s)│   per-folder loop │                           │
│                   ▼ │                 ▼ │                           │
├─────────────┬───────┼─────────┬────────┼───────────────────────────┤
│             │       ▼          │       ▼                           │
│ Dedicated thread - blocks to   │ Uses database inject/query         │
│ select_folder + idle_check()   │ queues cleanly                     │
└─────────────────────────────────────────────────────────────────────┘ 
``` 

### Why threading solves this architecture?
Previous hang issues arise due to...