---
layout: home

hero:
  name: "Google Workspace Secretary"
  text: "AI-Native MCP Server"
  tagline: Transform Gmail and Google Calendar into an intelligent, AI-powered knowledge base
  image:
    src: /hero-image.svg
    alt: Google Workspace Secretary MCP
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/johnneerdael/Google-Workspace-Secretary-MCP

features:
  - icon: ⚡
    title: Local-First Architecture
    details: v2.0 brings SQLite-backed instant reads. Email queries hit local cache instead of IMAP—sub-millisecond response times with background sync.
    
  - icon: 🤖
    title: AI-Native Design
    details: Built specifically for AI assistants like Claude via Model Context Protocol (MCP). Provides intelligent tools that scaffold complex email and calendar workflows.
    
  - icon: 🧠
    title: Intelligent Prioritization
    details: Daily briefings with ML-ready signals for VIP senders, urgency markers, questions, and deadlines. The AI decides priority based on your context.
    
  - icon: 🌍
    title: Timezone-Aware Scheduling
    details: All calendar operations respect your configured timezone and working hours. Automatically suggests meeting times that fit your schedule.
    
  - icon: 📄
    title: Document Intelligence
    details: Extract and analyze text from PDF, DOCX, TXT, and LOG attachments directly in the AI's context. No manual downloads needed.
    
  - icon: 🔒
    title: Human-in-the-Loop Safety
    details: Built-in safety patterns ensure all mutations (sending emails, deleting, moving) require explicit user confirmation.
---

## Quick Start

Install via Docker (recommended):

```yaml
# docker-compose.yml
services:
  workspace-secretary:
    image: ghcr.io/johnneerdael/google-workspace-secretary-mcp:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Read-only config
      - ./token.json:/app/token.json       # Read-write tokens
      - ./config:/app/config               # Cache databases
    restart: always
    command: ["--config", "/app/config.yaml", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
```

**Important**: Generate a unique bearer token for security:

```bash
# macOS/Linux
uuidgen

# Windows PowerShell
[guid]::NewGuid().ToString()
```

Add to your `config/config.yaml`:

```yaml
bearer_auth:
  enabled: true
  token: "your-generated-uuid-here"
```

Then start with: `docker-compose up -d`

See [Getting Started](/getting-started) for complete installation instructions.

## Why Google Workspace Secretary MCP?

Traditional email clients are built for humans. **Google Workspace Secretary MCP** is built for AI assistants.

- **Instant reads**: SQLite cache means sub-millisecond email queries (v2.0)
- **Token-efficient**: Bulk email fetching with smart truncation (700 chars) for fast triage
- **Context-rich**: Full thread history, attachment content, and calendar context in one tool call
- **Intelligence signals**: VIP detection, urgency markers, question detection—not hardcoded decisions
- **Agentic workflows**: Compose specialized agents (Triage, Scheduler, Intelligence Clerk) using atomic tools

## Example Workflows

::: tip Daily Briefing
"Give me my daily briefing—what emails need my attention today?"

The AI uses `get_daily_briefing()` to fetch:
- Today's calendar events
- Email candidates with 5 priority signals (VIP, urgent, questions, deadlines, meetings)
- Intelligent summary prioritizing your VIP senders and time-sensitive requests
:::

::: tip Smart Scheduling
"I received a meeting invite from John for tomorrow at 2 PM. Check my calendar and if I'm free during working hours, draft an acceptance."

The AI:
1. Checks calendar availability with `check_calendar()`
2. Validates time is within your `working_hours`
3. Uses `create_draft_reply()` to prepare response
4. Shows you the draft for confirmation
:::

::: tip Document Intelligence
"Find the invoice PDF sent by Accounting last week, read it, and tell me the total amount."

The AI:
1. Searches with `search_emails(keyword='invoice', from='accounting')`
2. Extracts PDF text with `get_attachment_content()`
3. Parses and presents the total
:::

## What's New in v2.2.0

**RFC 5256 Threading Support** — Full conversation threading with automatic backfill:

- 🧵 **Server-Side Threading**: Uses IMAP `THREAD` command (RFC 5256) when available for accurate parent/child relationships
- 🔄 **Automatic Backfill**: Existing emails automatically get thread headers populated on first sync after upgrade
- 📊 **Thread Data Model**: `in_reply_to`, `references`, `thread_root_uid`, `thread_parent_uid`, `thread_depth` stored in SQLite
- ⚡ **Cache-First Threads**: `get_email_thread` and `summarize_thread` now query local cache instead of IMAP
- 🔀 **Local Fallback**: Servers without THREAD support get local threading via References/In-Reply-To header analysis

See the [Threading Guide](/guide/threading) for details.

## What's New in v2.1.0

**Documentation & Bug Fixes**:

- 📚 Comprehensive v2.0 documentation overhaul
- 🔧 Fixed sync direction (newest-first for immediate usability)
- 🐛 Cache update fixes for triage tools

## What's New in v2.0.0

**Local-First Architecture** — The server now operates like a proper email client (Thunderbird, Apple Mail):

- ⚡ **SQLite Cache**: Email queries hit local database instead of IMAP—instant response times
- 🔄 **Background Sync**: Continuous incremental sync keeps your cache fresh (every 5 minutes)
- 💾 **Persistent Storage**: Cache survives restarts; only fetches new emails after initial sync
- 📊 **RFC-Compliant**: Proper UIDVALIDITY/UIDNEXT tracking per RFC 3501/4549

See the [Architecture Documentation](/architecture) for technical details.

## What's New in v1.1.0

- ✅ **Third-party OAuth Support** - Use Thunderbird/GNOME credentials
- ✅ **SMTP with XOAUTH2** - Send emails via authenticated SMTP
- ✅ **Calendar independent** - Google Calendar API works regardless of email backend

## What's New in v0.2.0

- ✅ **Timezone-aware scheduling** - All calendar operations use your configured timezone
- ✅ **Working hours constraints** - Meeting suggestions respect your work schedule
- ✅ **Intelligent email signals** - 5 ML-ready signals for AI-driven prioritization
- ✅ **VIP sender detection** - Configurable list of priority email addresses

[See Migration Guide](/guide/configuration#migration-from-v01x) for upgrading from earlier versions.

## Community & Support

- [GitHub Repository](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP)
- [Report Issues](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/issues)
- [View Releases](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/releases)

---

<div style="text-align: center; margin-top: 40px; color: var(--vp-c-text-2);">
  <p>Built with ❤️ for the AI-native future</p>
  <p style="font-size: 14px;">Licensed under MIT • © 2024-present John Neerdael</p>
</div>
