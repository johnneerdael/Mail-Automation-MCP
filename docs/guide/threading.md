# Email Threading (v2.2.0)

Gmail Secretary v2.2.0 introduces full RFC 5256 threading support, enabling accurate conversation grouping with automatic migration for existing databases.

## Overview

Email threading groups related messages into conversations. This is essential for:

- Understanding email context without reading each message individually
- AI agents summarizing entire conversations
- Identifying the latest response in a thread

## How Threading Works

### Server-Side Threading (RFC 5256)

When your IMAP server supports the `THREAD` extension, we use it for accurate parent/child relationships:

```
IMAP Server → THREAD REFERENCES UTF-8 ALL
            ← * THREAD (2)(3 6 (4 23)(44 7 96))
```

The response encodes thread hierarchy:
- Thread 1: Message 2 (standalone)
- Thread 2: 3 → 6 → branches to (4 → 23) and (44 → 7 → 96)

Gmail's IMAP server supports `THREAD=REFERENCES`.

### Local Threading Fallback

For servers without `THREAD` support, we build the thread index locally using:

1. **In-Reply-To** header: Points to the immediate parent message
2. **References** header: Lists all ancestor Message-IDs

This achieves the same result, just computed client-side instead of server-side.

## Thread Data Model

Each email in the SQLite cache stores:

| Column | Description |
|--------|-------------|
| `in_reply_to` | Message-ID this email replies to |
| `references` | Space-separated list of ancestor Message-IDs |
| `thread_root_uid` | UID of the first message in the thread |
| `thread_parent_uid` | UID of the direct parent message |
| `thread_depth` | Nesting level (0 = root, 1 = first reply, etc.) |

### Example Thread Structure

```
Email A (thread_root_uid=100, thread_parent_uid=NULL, thread_depth=0)
├── Email B (thread_root_uid=100, thread_parent_uid=100, thread_depth=1)
│   └── Email D (thread_root_uid=100, thread_parent_uid=101, thread_depth=2)
└── Email C (thread_root_uid=100, thread_parent_uid=100, thread_depth=1)
```

## Automatic Backfill

When upgrading from v2.1.x or earlier, your existing emails lack thread headers. The system handles this automatically:

### Migration Flow

```
Container Start
      ↓
sync_folder() called
      ↓
Detect emails with empty in_reply_to/references
      ↓
Fetch ONLY headers from IMAP (fast - no body re-download)
      ↓
Update SQLite with thread headers
      ↓
Build thread index
```

### What You'll See in Logs

```
[BACKFILL] Fetching thread headers for 26000 emails in INBOX
[BACKFILL] Progress: 100/26000 headers fetched
[BACKFILL] Progress: 200/26000 headers fetched
...
[BACKFILL] Complete: 26000 emails updated with thread headers
[BACKFILL] Building thread index for INBOX
```

### Performance

| Emails | Backfill Time | Notes |
|--------|---------------|-------|
| 1,000 | ~30 seconds | Headers only, no body |
| 10,000 | ~5 minutes | Batched in groups of 100 |
| 25,000 | ~12 minutes | One-time operation |

After backfill completes, thread queries are instant (SQLite).

## Using Thread Tools

### get_email_thread

Retrieves all emails in a conversation:

```json
{
  "tool": "get_email_thread",
  "arguments": {
    "folder": "INBOX",
    "uid": 12345
  }
}
```

Returns emails sorted by date with threading context.

### summarize_thread

Gets thread with content for AI summarization:

```json
{
  "tool": "summarize_thread", 
  "arguments": {
    "thread_id": "12345"
  }
}
```

Returns participant count, message count, and full content (truncated to 2000 chars per message).

## Cache-First Architecture

All thread operations now query SQLite first:

```
get_email_thread(uid=123)
        ↓
cache.get_thread_emails(123, "INBOX")
        ↓
Follow references chain in SQLite
        ↓
Return all related emails (instant)
        ↓
[IMAP fallback only if cache unavailable]
```

### Performance Comparison

| Operation | Before v2.2.0 | After v2.2.0 |
|-----------|---------------|--------------|
| Get thread (10 emails) | 2-5 seconds (N IMAP queries) | < 50ms (1 SQLite query) |
| Summarize thread | 3-8 seconds | < 100ms |

## Server Capability Detection

The system automatically detects server capabilities:

```python
# Check if THREAD is supported
client.has_thread_capability("REFERENCES")  # True for Gmail

# Check if SORT is supported  
client.has_sort_capability()  # True for most servers
```

### Supported Threading Algorithms

| Algorithm | Description | Support |
|-----------|-------------|---------|
| `REFERENCES` | Full parent/child threading via References header | Gmail ✅ |
| `ORDEREDSUBJECT` | Groups by normalized subject line | Most servers |

We prefer `REFERENCES` when available for accurate threading.

## Troubleshooting

### Thread Not Grouping Correctly

Some emails lack proper `In-Reply-To` or `References` headers (e.g., composed in webmail without proper threading). These will appear as separate threads.

### Backfill Seems Stuck

Check Docker logs for progress:

```bash
docker logs workspace-secretary 2>&1 | grep BACKFILL
```

Each batch of 100 emails logs progress. Large mailboxes take time but will complete.

### Thread Index Not Building

If you see `Failed to build thread index`, the IMAP server may have disconnected. The next sync cycle will retry automatically.

## Technical Details

### RFC References

- **RFC 5256**: IMAP SORT and THREAD Extensions
- **RFC 2822**: Message-ID, In-Reply-To, References headers
- **RFC 5322**: Internet Message Format (updated)

### SQLite Indexes

Thread queries are optimized with:

```sql
CREATE INDEX idx_thread_root ON emails(thread_root_uid);
CREATE INDEX idx_in_reply_to ON emails(in_reply_to);
CREATE INDEX idx_message_id ON emails(message_id);
```
