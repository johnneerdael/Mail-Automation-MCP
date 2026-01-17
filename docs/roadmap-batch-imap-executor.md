# Batch IMAP Executor (Process) Roadmap

## Goal
Move heavy IMAP batch work (sync + later mutations) off the main FastAPI/LangGraph process into a **separate executor process** while keeping:

- **UI 100% responsive** (no browser lockups)
- **SSE progress updates** identical in shape/semantics to current `batch_progress` / `batch_complete`
- **LangGraph checkpointing** intact (no state corruption)
- **HITL** for **all mutations** (per `AGENTS.md`)

This roadmap documents **all phases**, but Phase 1 is the target for immediate implementation.

---

## Phase 1 (NOW): Postgres-backed Job Queue + Separate IMAP Executor Process

### Outcome
- New service `imap-executor` runs in Docker Compose.
- Main web process can enqueue a job (`sync` first), then stream its progress over SSE without blocking.
- Executor claims jobs via Postgres row locking and writes progress events back to Postgres.

### Why this works
- Main process becomes **pure orchestration** (enqueue + stream), avoiding long, blocking IMAP work.
- Executor owns IMAP connections (Gmail allows enough connections to run multiple jobs concurrently).
- Postgres is already in the stack; no new infra.

### Architecture

**Components**
1. **Main web process** (`workspace-secretary`)
   - Creates job rows in Postgres.
   - Streams job events over SSE by polling Postgres.
   - (Later phases) enqueues mutation jobs only after explicit user confirmation.

2. **IMAP executor process** (`imap-executor`)
   - Claims jobs from Postgres using `SELECT ... FOR UPDATE SKIP LOCKED`.
   - Executes IMAP work using a dedicated IMAP connection.
   - Writes progress to Postgres frequently.

**Job storage**
- `imap_jobs` table: job metadata + counters + status.
- `imap_job_events` table: append-only progress/event log (supports replay after reconnect).

### Job lifecycle
- `pending` → `running` → `completed | failed | cancelled`

### Concurrency
- Executor runs with a fixed worker pool (start with **3 workers**).
- Each worker uses its own IMAP connection.
- Claiming is safe under concurrency due to row locking.

### Cancellation
- Web sets `cancel_requested=true`.
- Executor checks between micro-batches and transitions to `cancelled`.

### SSE event format
SSE endpoint streams JSON lines in `data:` payloads.

- `job_event` (append-only log events)
- `job_status` (snapshot)
- `heartbeat`

The frontend can either display these directly or the chat layer can map them into existing `batch_progress` / `batch_complete` events.

### Phase 1 Test Cases

#### Unit / integration (Python-level)
1. Create job → executor claims → status transitions to completed.
2. Progress increments over time (processed counters increase monotonically).
3. Cancel requested while running → executor stops and job ends cancelled.
4. Failure (simulated IMAP error) → job status failed, error captured, event emitted.

#### E2E (Docker + HTTP)
1. Start stack, enqueue job, watch SSE events stream without delay.
2. Confirm UI remains responsive during long job (scroll/type while progress updates).
3. Run 3 jobs concurrently; each has independent events and no cross-stream contamination.

---

## Phase 2: Wire `/clean` mutations into executor (still HITL)

### Outcome
- `/clean` discovery remains read-only.
- The actual mutation step (`execute_clean_batch`) becomes an executor job.
- Progress and completion events are streamed from Postgres.

### Safety
- Main process only enqueues mutation jobs after explicit user approval.

---

## Phase 3: Tighten `/clean` candidate criteria (no direct-To emails)

### Outcome
- `quick_clean_inbox` excludes any email where user is in `To:`/`CC:` or name mentioned, consistent with `AGENTS.md` safety guarantees.
- Fix reported case: directly-addressed email (e.g. `aroy@netskope.com`) never becomes a cleanup candidate.

### Tests
- Golden-case fixture email: To:user → excluded.
- Newsletter → included.

---

## Phase 4: Priority scoring exposure + robust filters

### Outcome
- Expose numeric confidence/score in triage tool outputs.
- Add helper tool to return “top N by confidence” and support filters:
  - today
  - unread
  - zoom-related

### Tests
- Tool returns sorted output and obeys filters.
- Chat prompt: “top 10 highest-confidence action-required from today” triggers tool call and gives correct list.

---

## Phase 5: Mutation capability clarity + tooling

### Outcome
- System prompt and tools make it explicit Piper can:
  - mark read/unread
  - move
  - apply labels (including `Secretary/Auto-Cleaned`)
- Always HITL for mutations; executor just executes approved jobs.

---

## Implementation Notes

- Avoid changing `config.yaml`.
- Prefer minimal changes: add new modules + routes, keep existing chat stream stable.
- Use Postgres row locking for job claiming.
- Start with `sync` jobs (read/ingest) to prove non-blocking execution; expand to mutation jobs in Phase 2.
