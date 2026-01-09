# Getting Started

Get up and running with Google Workspace Secretary MCP in minutes.

## Prerequisites

Before you begin, ensure you have:

- **Docker and Docker Compose** installed (recommended method)
  - [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Google Cloud Project** (if using Gmail/Google Calendar)
  - Gmail API and Google Calendar API enabled
  - OAuth2 credentials (`credentials.json`)
- **Claude Desktop** or another MCP-compatible AI client

## Installation Methods

### Method 1: Docker (Recommended)

The easiest and most reliable way to run the server.

**1. Pull the Docker image:**

```bash
docker pull ghcr.io/johnneerdael/google-workspace-secretary-mcp:latest
```

**2. Create your configuration:**

Create a `config.yaml` file (see [Configuration Guide](/guide/configuration)):

```yaml
oauth_mode: api  # or "imap" for third-party OAuth

identity:
  email: your-email@gmail.com
  full_name: "Your Name"

imap:
  host: imap.gmail.com
  port: 993
  username: your-email@gmail.com
  use_ssl: true
  oauth2:
    client_id: YOUR_CLIENT_ID.apps.googleusercontent.com
    client_secret: YOUR_CLIENT_SECRET

timezone: America/Los_Angeles

working_hours:
  start: "09:00"
  end: "17:00"
  workdays: [1, 2, 3, 4, 5]

vip_senders:
  - boss@company.com
  - ceo@company.com
```

**3. Create `docker-compose.yml`:**

```yaml
services:
  workspace-secretary:
    image: ghcr.io/johnneerdael/google-workspace-secretary-mcp:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config/config.yaml
      - ./credentials.json:/app/credentials.json  # For OAuth2
      - ./token.json:/app/token.json  # OAuth2 token (auto-generated)
    environment:
      - WORKSPACE_TIMEZONE=America/Los_Angeles
      - WORKING_HOURS_START=09:00
      - WORKING_HOURS_END=17:00
      - VIP_SENDERS=boss@company.com,ceo@company.com
    restart: always
```

**4. Start the server:**

```bash
docker-compose up -d
```

**5. Authenticate (OAuth2 only):**

If using OAuth2 (recommended for Gmail), run the authentication flow:

```bash
docker exec -it workspace-secretary uv run python -m workspace_secretary.auth_setup --config /app/config/config.yaml
```

Follow the prompts to authorize the application. The `token.json` will be created automatically.

See [Docker Guide](/guide/docker) for advanced Docker configuration.

### Method 2: Local Development

For development or if you prefer running without Docker.

**1. Clone the repository:**

```bash
git clone https://github.com/johnneerdael/Google-Workspace-Secretary-MCP.git
cd Google-Workspace-Secretary-MCP
```

**2. Install dependencies with `uv`:**

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

**3. Configure:**

Copy `config.sample.yaml` to `config.yaml` and edit:

```bash
cp config.sample.yaml config.yaml
# Edit config.yaml with your details
```

**4. Authenticate (if using OAuth2):**

```bash
python -m workspace_secretary.auth_setup --config config.yaml
```

**5. Run the server:**

```bash
python -m workspace_secretary.server
```

The server will start on `http://localhost:8000`.

## Google Cloud Setup

If you're using Gmail and Google Calendar, you need to set up a Google Cloud Project.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Gmail API** and **Google Calendar API**:
   - Navigate to **APIs & Services** > **Library**
   - Search for "Gmail API" and click **Enable**
   - Search for "Google Calendar API" and click **Enable**

### Step 2: Create OAuth2 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Configure the consent screen if prompted:
   - User type: **External** (or Internal if using Google Workspace)
   - Add your email as a test user
   - Scopes: Add Gmail and Calendar scopes (the tool will request these during auth)
4. Application type: **Desktop app**
5. Download the credentials JSON file and save it as `credentials.json`

### Step 3: Run the Authentication Flow

The first time you run the server, you'll need to authenticate:

```bash
# Docker
docker exec -it workspace-secretary uv run python -m workspace_secretary.auth_setup --config /app/config/config.yaml

# Local
python -m workspace_secretary.auth_setup --config config.yaml
```

This will:
1. Open a browser window for Google OAuth consent
2. Ask you to grant permissions (read/write Gmail, read/write Calendar)
3. Save a `token.json` file for future use

## Connecting to Claude Desktop

Once the server is running, connect it to Claude Desktop via MCP.

**1. Edit Claude Desktop config:**

On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

On Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**2. Add the MCP server:**

```json
{
  "mcpServers": {
    "workspace-secretary": {
      "command": "docker",
      "args": ["exec", "-i", "workspace-secretary", "uv", "run", "python", "-m", "workspace_secretary.server"],
      "env": {}
    }
  }
}
```

**Alternatively, for local development:**

```json
{
  "mcpServers": {
    "workspace-secretary": {
      "command": "python",
      "args": ["-m", "workspace_secretary.server"],
      "env": {
        "CONFIG_PATH": "/absolute/path/to/config.yaml"
      }
    }
  }
}
```

**3. Restart Claude Desktop**

Claude will now have access to all Google Workspace Secretary tools.

## Verify Installation

Test the connection by asking Claude:

> "Use the workspace secretary to get my unread emails"

You should see Claude use the `get_unread_messages` tool and return your recent unread emails.

## Next Steps

- [Configure your settings](/guide/configuration) in detail
- Learn [Agent Patterns](/guide/agents) for building intelligent workflows
- Explore [Use Cases](/guide/use-cases) for inspiration
- Check out the [API Reference](/api/) for all available tools

## Troubleshooting

### OAuth2 Authentication Fails

**Problem**: Browser shows "This app isn't verified"

**Solution**: Click "Advanced" > "Go to [Your App Name] (unsafe)". This is normal for development apps not published to Google.

### Docker Container Won't Start

**Problem**: `Error: config.yaml not found`

**Solution**: Ensure your `docker-compose.yml` volume paths are correct and `config.yaml` exists in the current directory.

### Tool Calls Fail with "Permission Denied"

**Problem**: Claude can't access Gmail/Calendar

**Solution**: 
1. Verify `token.json` exists and is valid
2. Re-run the auth setup: `docker exec -it workspace-secretary uv run python -m workspace_secretary.auth_setup --config /app/config/config.yaml`
3. Check that Gmail/Calendar APIs are enabled in Google Cloud Console

### Timezone Issues

**Problem**: Meeting times don't respect my working hours

**Solution**: Verify your `timezone` field in `config.yaml` uses a valid IANA timezone (e.g., `America/Los_Angeles`, not `PST`).

---

**Need more help?** [Open an issue on GitHub](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP/issues)
