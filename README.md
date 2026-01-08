# IMAP MCP Server

A Model Context Protocol (MCP) server that enables AI assistants to check email, process messages, and learn user preferences through interaction.

## Overview

This project implements an MCP server that interfaces with IMAP email servers to provide the following capabilities:

- Email browsing and searching
- Email organization (moving, tagging, marking)
- Email composition and replies
- Interactive email processing and learning user preferences
- Automated email summarization and categorization
- Support for multiple IMAP providers

The IMAP MCP server is designed to work with Claude or any other MCP-compatible assistant, allowing them to act as intelligent email assistants that learn your preferences over time.

## Features
- **Read Emails**: Search and read emails from specific folders (default: INBOX)
- **Send Emails**: Send new emails with optional attachments
- **Organize**: Move, copy, and delete emails; manage folders
- **Triage**: AI-ready tools for analyzing email importance and content
- **Security**:
  - OAuth2 support for Gmail/Outlook
  - Bearer Token authentication for HTTP MCP connections
- **Deployment**: Docker support with health checks and persistent configuration

## Current Project Structure

The project is currently organized as follows:

```
.
├── examples/              # Example configurations
│   └── config.yaml.example
├── imap_mcp/              # Source code
│   ├── __init__.py
│   ├── config.py          # Configuration handling
│   ├── imap_client.py     # IMAP client implementation
│   ├── models.py          # Data models
│   ├── resources.py       # MCP resources implementation
│   ├── server.py          # Main server implementation
│   └── tools.py           # MCP tools implementation
├── tests/                 # Test suite
│   ├── __init__.py
│   └── test_models.py
├── INSTALLATION.md        # Detailed installation guide
├── pyproject.toml         # Project configuration
└── README.md              # This file
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- An IMAP-enabled email account (Gmail recommended)
- [uv](https://docs.astral.sh/uv/) for package management and running Python scripts

### Installation

1. Install uv if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and install the package:
   ```bash
   git clone https://github.com/non-dirty/imap-mcp.git
   cd imap-mcp
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

### Gmail Configuration

1. Create a config file:
   ```bash
   cp config.sample.yaml config.yaml
   ```

2. Set up Gmail OAuth2 credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable the Gmail API
   - Create OAuth2 credentials (Desktop Application type)
   - Download the client configuration

3. Update `config.yaml` with your Gmail settings:
   ```yaml
   imap:
     host: imap.gmail.com
     port: 993
     username: your-email@gmail.com
     use_ssl: true
     oauth2:
       client_id: YOUR_CLIENT_ID
       client_secret: YOUR_CLIENT_SECRET
       refresh_token: YOUR_REFRESH_TOKEN
   ```

### Usage

#### Checking Email

To list emails in your inbox:
```bash
uv run list_inbox.py --config config.yaml --folder INBOX --limit 10
```

Available options:
- `--folder`: Specify which folder to check (default: INBOX)
- `--limit`: Maximum number of emails to display (default: 10)
- `--verbose`: Enable detailed logging output

#### Starting the MCP Server

To start the IMAP MCP server:
```bash
uv run imap_mcp.server --config config.yaml
```

For development mode with debugging:
```bash
uv run imap_mcp.server --dev
```

#### Managing OAuth2 Tokens

To refresh your OAuth2 token:
```bash
uv run imap_mcp.auth_setup refresh-token --config config.yaml
```

To generate a new OAuth2 token:
```bash
uv run imap_mcp.auth_setup generate-token --config config.yaml
```

## Available Tools

The following tools are available to the AI agent:

| Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| **`search_emails`** | Searches for emails across folders. | `query`, `folder` (opt), `criteria` (text/from/subject/etc), `limit` |
| **`process_email`** | Performs an action on an email (move, read, flag, delete). | `folder`, `uid`, `action`, `target_folder` (for move) |
| **`process_meeting_invite`** | **(Smart Workflow)** Identifies meeting invites, checks availability, and drafts a reply. | `folder`, `uid`, `availability_mode` |
| **`draft_reply_tool`** | Creates a draft reply to an email. | `folder`, `uid`, `reply_body`, `reply_all`, `cc` |
| **`create_task`** | Creates a local task from email content. | `description`, `due_date`, `priority` |
| **`move_email`** | Moves an email to another folder. | `folder`, `uid`, `target_folder` |
| **`mark_as_read`** | Marks an email as read. | `folder`, `uid` |
| **`mark_as_unread`** | Marks an email as unread. | `folder`, `uid` |
| **`flag_email`** | Flags (stars) an email. | `folder`, `uid`, `flag` (bool) |
| **`delete_email`** | Deletes an email. | `folder`, `uid` |
| **`draft_meeting_reply_tool`** | Low-level tool to draft a meeting reply. | `invite_details`, `availability_status` |
| **`check_calendar_availability_tool`** | Low-level tool to check calendar availability. | `start_time`, `end_time` |
| **`identify_meeting_invite_tool`** | Low-level tool to parse invite details. | `folder`, `uid` |

## Development

### Setting Up Development Environment

```bash
# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## Security Considerations

This MCP server requires access to your email account, which contains sensitive personal information. Please be aware of the following security considerations:

- Store email credentials securely using environment variables or secure credential storage
- Consider using app-specific passwords instead of your main account password
- Limit folder access to only what's necessary for your use case
- Review the permissions granted to the server in your email provider's settings

## Project Roadmap

- [x] Project initialization and repository setup
- [x] Basic IMAP integration
- [x] Email resource implementation
- [x] Email tool implementation
- [x] Email reply and draft functionality
- [ ] User preference learning implementation
- [ ] Advanced search capabilities
- [ ] Multi-account support
- [ ] Integration with major email providers

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) for providing the framework
- [Anthropic](https://www.anthropic.com/) for developing Claude
- Various Python IMAP libraries that make this project possible
