# Gmail Secretary MCP

[![Version](https://img.shields.io/badge/version-4.1.0-blue.svg)](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An AI-native Model Context Protocol (MCP) server that transforms your Gmail and Google Calendar into an intelligent, programmable assistant for Claude and other AI systems.

[📚 **Full Documentation**](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/) · [🚀 **Quick Start**](#-quick-start) · [🔒 **Security**](#-security-best-practices)

---

## What's New in v4.1.0

**CONDSTORE & IDLE Support** — Efficient incremental sync with push notifications:

- ⚡ **CONDSTORE (RFC 7162)**: Skip sync when mailbox unchanged, fetch only changed flags
- 📬 **IMAP IDLE (RFC 2177)**: Push-based notifications for instant new mail detection
- 🏷️ **Gmail Extensions**: Native X-GM-MSGID, X-GM-THRID, X-GM-LABELS support
- 📎 **Attachment Metadata**: `has_attachments` and `attachment_filenames` in database
- 🔄 **Debounced Sync**: Mutations trigger 2-second debounced sync to batch changes

### Performance Improvements

| Scenario | Before | After |
|----------|--------|-------|
| Unchanged mailbox | Fetch all UIDs, compare | Skip entirely (HIGHESTMODSEQ) |
| Flag changes only | Re-fetch entire message | Fetch only changed flags (CHANGEDSINCE) |
| New mail detection | 5-minute poll interval | Instant via IDLE |
| Rapid mutations | Sync per mutation | Single batched sync |

See the [Architecture Documentation](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/architecture.html) for details.

---

## What's New in v4.0.0

### Complete Architecture Rewrite

This release fundamentally changes how the system works internally. The Engine now owns **all database writes**, while the MCP server is **read-only** against the database.

### Changed

- **Engine owns all database writes**: Engine now uses `DatabaseInterface` (not legacy `EmailCache`) for all persistence
- **MCP is read-only**: MCP server reads directly from database, calls Engine API only for mutations
- **Unified database access**: Both Engine and MCP use the same `DatabaseInterface` abstraction
- **Database backend selection**: `config.database.backend` determines SQLite or PostgreSQL for both processes

### Added

- **New Engine API endpoints**:
  - `GET /api/calendar/events` - List calendar events in time range
  - `GET /api/calendar/availability` - Get free/busy information
  - `POST /api/email/setup-labels` - Create Secretary label hierarchy in Gmail
  - `POST /api/email/send` - Send email via Gmail API
  - `POST /api/email/draft-reply` - Create draft reply to an email
- **Calendar sync in Engine**: `sync_loop()` now syncs both email and calendar
- **Automatic embedding generation**: Engine generates embeddings after email sync (PostgreSQL + pgvector)
- **Graceful enrollment**: Engine starts in "no account" mode and auto-connects when OAuth tokens appear

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Server    │────▶│  SQLite/PG DB   │◀────│     Engine      │
│  (read-only)    │     │  (unified)      │     │  (all writes)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        └──────────────▶ Engine FastAPI ◀───────────────┘
                        (mutations only)
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Intelligent Triage** | Auto-detect VIPs, questions, deadlines, and meeting requests |
| **Timezone-Aware Scheduling** | All calendar ops respect your configured timezone and working hours |
| **Document Intelligence** | Extract content from PDF/DOCX attachments directly into AI context |
| **Safe Actions** | "Draft First" philosophy — AI never sends without your approval |
| **Local-First Cache** | SQLite-backed instant reads with background IMAP sync |

---

## 🚀 Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/johnneerdael/Google-Workspace-Secretary-MCP.git
cd Google-Workspace-Secretary-MCP

# Create your config
cp config.sample.yaml config/config.yaml
```

### 2. Generate a Secure Bearer Token

**We strongly recommend enabling bearer authentication.** Generate a unique token:

```bash
# macOS / Linux
uuidgen

# Windows (PowerShell)
[guid]::NewGuid().ToString()

# Or use OpenSSL for a longer token
openssl rand -hex 32
```

Add to your `config/config.yaml`:

```yaml
bearer_auth:
  enabled: true
  token: "your-generated-uuid-here"
```

### 3. Configure Email Credentials

Edit `config/config.yaml` with your IMAP/SMTP details:

```yaml
email:
  imap_server: imap.gmail.com
  smtp_server: smtp.gmail.com
  username: your-email@gmail.com
  password: your-app-password  # Use Gmail App Password, not your main password
```

> 💡 **Gmail Users**: You need an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 4. Start with Docker

```bash
docker-compose up -d
```

The server exposes a **Streamable HTTP** endpoint at: `http://localhost:8000/mcp`

### 5. Connect Your AI Client

Configure your MCP client to connect:

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "secretary": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-generated-uuid-here"
      }
    }
  }
}
```

See the [Client Setup Guide](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/getting-started.html) for VS Code, Cursor, and other clients.

---

## 🔒 Security Best Practices

| Practice | Why |
|----------|-----|
| **Always enable bearer auth** | Prevents unauthorized access to your email |
| **Use a UUID token** | Cryptographically random, not guessable |
| **Never commit config.yaml** | Contains secrets — it's in `.gitignore` |
| **Use Gmail App Passwords** | Don't expose your main Google password |
| **Run behind firewall** | Don't expose port 8000 to public internet |

See the [Security Guide](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/guide/security.html) for SSL/TLS setup and advanced security.

---

## 🤖 Usage Examples

Once connected, ask your AI assistant:

```
"Give me my daily briefing"
→ Summarizes priority emails, today's calendar, and pending action items

"Triage my inbox - what needs attention?"
→ Identifies VIP messages, questions directed at you, and deadline mentions

"Draft a reply to Sarah's meeting request accepting for Tuesday"
→ Creates a draft (never sends automatically) for your review

"What's on my calendar this week?"
→ Lists events with timezone-aware times

"Find all emails from John about the Q4 report"
→ Searches local cache for instant results
```

---

## 📁 Project Structure

```
Google-Workspace-Secretary-MCP/
├── config/
│   ├── config.yaml          # Your configuration (git-ignored)
│   ├── email_cache.db       # SQLite email cache (auto-created)
│   └── calendar_cache.db    # SQLite calendar cache (auto-created)
├── workspace_secretary/
│   ├── server.py            # MCP server
│   ├── tools.py             # All MCP tools
│   ├── engine/              # Sync engine (v3.0.0)
│   │   ├── api.py           # Internal API (Unix socket)
│   │   ├── imap_sync.py     # IMAP client and sync
│   │   ├── calendar_sync.py # Calendar client and sync
│   │   ├── email_cache.py   # Email SQLite cache
│   │   └── calendar_cache.py# Calendar SQLite cache
│   └── engine_client.py     # MCP → Engine communication
├── docs/                    # VitePress documentation
├── docker-compose.yaml      # Dual-process deployment
└── config.sample.yaml       # Template config
```

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/getting-started.html) | Full installation and client setup |
| [Configuration](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/guide/configuration.html) | All config.yaml options explained |
| [Docker Guide](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/guide/docker.html) | Container setup and volume persistence |
| [Architecture](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/architecture.html) | v2.0 local-first design and SQLite schema |
| [Security](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/guide/security.html) | Bearer auth, SSL, and best practices |
| [Agent Workflows](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/guide/agents.html) | HITL rules and safe action patterns |
| [API Reference](https://johnneerdael.github.io/Google-Workspace-Secretary-MCP/api/) | All available tools and resources |

---

## 🛠️ Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run locally (without Docker)
python -m workspace_secretary.server
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

Built with the [Model Context Protocol](https://modelcontextprotocol.io/) · [GitHub](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP)
