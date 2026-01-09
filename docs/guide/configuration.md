# Configuration

Complete configuration reference for Google Workspace Secretary MCP.

## Configuration File

The server requires a `config.yaml` file. Copy `config.sample.yaml` as a starting point.

## Required Fields

### OAuth Mode

```yaml
oauth_mode: api  # or "imap"
```

**Options:**
- `api` (default): Uses Gmail REST API. Requires your own GCP OAuth credentials.
- `imap`: Uses IMAP/SMTP protocols. Works with third-party OAuth credentials (Thunderbird, GNOME).

See [OAuth Workaround](./oauth_workaround) for using third-party credentials.

### User Identity

```yaml
identity:
  email: your-email@gmail.com
  full_name: "Your Full Name"
  aliases:
    - alternate@gmail.com
    - work@company.com
```

**Fields:**
- `email` (required): Your primary email address
- `full_name` (optional): Used to detect if you're mentioned in email body
- `aliases` (optional): Additional email addresses you use

**Used by:**
- `get_daily_briefing`: Signals `is_addressed_to_me` and `mentions_my_name`
- `quick_clean_inbox`: Determines which emails can be auto-cleaned

### IMAP Configuration

```yaml
imap:
  host: imap.gmail.com  # IMAP server hostname
  port: 993             # IMAP port (993 for SSL)
  username: your-email@gmail.com
  use_ssl: true         # Use SSL/TLS encryption
  
  # OAuth2 (recommended for Gmail)
  oauth2:
    client_id: YOUR_CLIENT_ID.apps.googleusercontent.com
    client_secret: YOUR_CLIENT_SECRET
  
  # OR password auth (less secure)
  # password: your-app-specific-password
```

**For Gmail**: Use OAuth2 for best security. Create credentials in [Google Cloud Console](https://console.cloud.google.com/).

### Timezone

```yaml
timezone: America/Los_Angeles  # IANA timezone format
```

**Valid formats**: [IANA Time Zone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) names:
- `America/Los_Angeles` (not `PST`)
- `Europe/London` (not `GMT`)
- `Asia/Tokyo` (not `JST`)

### Working Hours

```yaml
working_hours:
  start: "09:00"  # HH:MM format, 24-hour clock
  end: "17:00"    # HH:MM format, 24-hour clock
  workdays: [1, 2, 3, 4, 5]  # 1=Monday, 7=Sunday
```

**Rules**:
- Times must be in `HH:MM` format (e.g., `09:00`, not `9:00 AM`)
- Workdays: `1`=Monday through `7`=Sunday
- Tools like `suggest_reschedule()` only suggest times within these constraints

### VIP Senders

```yaml
vip_senders:
  - boss@company.com
  - ceo@company.com
  - important-client@example.com
```

**Rules**:
- Exact email addresses (case-insensitive)
- Emails from these senders get `is_from_vip=true` in daily briefings

## Optional Fields

### Allowed Folders

Restrict which folders the AI can access:

```yaml
allowed_folders:
  - INBOX
  - Sent
  - Archive
  - "[Gmail]/All Mail"
```

**Default**: If omitted, all folders are accessible.

### Calendar Configuration

```yaml
calendar:
  enabled: true  # Enable calendar tools
  verified_client: your-email@gmail.com  # Email for calendar operations
```

**Default**: Calendar tools disabled unless explicitly enabled.

### SMTP Configuration

For sending emails:

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  username: your-email@gmail.com
  use_tls: true
  # password or oauth2 (same as IMAP)
```

**Default**: Uses IMAP credentials if omitted.

## Environment Variables

All fields can be overridden via environment variables. Useful for Docker deployments.

### Core Variables

| Variable | Config Path | Default | Example |
|----------|-------------|---------|---------|
| `IMAP_HOST` | `imap.host` | - | `imap.gmail.com` |
| `IMAP_PORT` | `imap.port` | `993` | `993` |
| `IMAP_USERNAME` | `imap.username` | - | `user@gmail.com` |
| `IMAP_PASSWORD` | `imap.password` | - | `app-password` |
| `IMAP_USE_SSL` | `imap.use_ssl` | `true` | `true` |
| `WORKSPACE_TIMEZONE` | `timezone` | `UTC` | `America/New_York` |
| `WORKING_HOURS_START` | `working_hours.start` | `09:00` | `08:30` |
| `WORKING_HOURS_END` | `working_hours.end` | `17:00` | `18:00` |
| `WORKING_HOURS_DAYS` | `working_hours.workdays` | `1,2,3,4,5` | `1,2,3,4,5` |
| `VIP_SENDERS` | `vip_senders` | - | `boss@co.com,ceo@co.com` |
| `IMAP_ALLOWED_FOLDERS` | `allowed_folders` | - | `INBOX,Sent,Archive` |

### OAuth2 Variables

| Variable | Config Path | Example |
|----------|-------------|---------|
| `OAUTH2_CLIENT_ID` | `imap.oauth2.client_id` | `123.apps.googleusercontent.com` |
| `OAUTH2_CLIENT_SECRET` | `imap.oauth2.client_secret` | `GOCSPX-...` |

### Docker Example

```yaml
# docker-compose.yml
services:
  workspace-secretary:
    image: ghcr.io/johnneerdael/google-workspace-secretary-mcp:latest
    environment:
      - WORKSPACE_TIMEZONE=America/Los_Angeles
      - WORKING_HOURS_START=09:00
      - WORKING_HOURS_END=17:00
      - WORKING_HOURS_DAYS=1,2,3,4,5
      - VIP_SENDERS=boss@company.com,ceo@company.com
      - IMAP_USERNAME=user@gmail.com
      - OAUTH2_CLIENT_ID=YOUR_ID.apps.googleusercontent.com
      - OAUTH2_CLIENT_SECRET=YOUR_SECRET
```

## Migration from v0.1.x

Version 0.2.0 introduced **breaking changes**. You must add these required fields:

```yaml
# Add to your existing config.yaml:

timezone: "UTC"  # Or your preferred timezone

working_hours:
  start: "09:00"
  end: "17:00"
  workdays: [1, 2, 3, 4, 5]

vip_senders: []  # Empty list if you don't have VIPs
```

**API Changes**:
- `get_daily_briefing()` now returns `email_candidates` (not `priority_emails`)
- `suggest_reschedule()` respects `working_hours` and `timezone`

## Validation

The server validates your config on startup:

- **Timezone**: Must be a valid IANA timezone (raises error if invalid)
- **Working Hours**: Times must be `HH:MM` format
- **Workdays**: Must be integers 1-7
- **VIP Senders**: Normalized to lowercase for matching

**Example error**:
```
ValueError: Invalid timezone: 'PST'. Use IANA format like 'America/Los_Angeles'
```

## Configuration Precedence

Order of precedence (highest to lowest):
1. Environment variables
2. `config.yaml` file
3. Default values

## Security Best Practices

### OAuth2 (Recommended)

✅ Use OAuth2 for Gmail/Google Workspace:
- More secure than app passwords
- Supports token refresh
- Can be revoked via Google Account settings

### App Passwords (Less Secure)

If OAuth2 isn't available:
```yaml
imap:
  password: your-app-specific-password  # Generate in Google Account settings
```

❌ **Never commit credentials to version control!**

### Credentials Management

**For Docker:**
```bash
# Use Docker secrets or environment variables
docker run -e IMAP_PASSWORD="$GMAIL_APP_PASSWORD" ...
```

**For local development:**
```bash
# Use .env file (add to .gitignore)
export IMAP_PASSWORD="..."
```

## Example Configurations

### Gmail with OAuth2

```yaml
imap:
  host: imap.gmail.com
  port: 993
  username: user@gmail.com
  use_ssl: true
  oauth2:
    client_id: 123456.apps.googleusercontent.com
    client_secret: GOCSPX-abcdef123456

timezone: America/New_York

working_hours:
  start: "08:00"
  end: "18:00"
  workdays: [1, 2, 3, 4, 5]

vip_senders:
  - manager@company.com
  - ceo@company.com

calendar:
  enabled: true
  verified_client: user@gmail.com
```

### Generic IMAP with Password

```yaml
imap:
  host: mail.example.com
  port: 993
  username: john@example.com
  password: my-secure-password
  use_ssl: true

timezone: Europe/London

working_hours:
  start: "09:00"
  end: "17:00"
  workdays: [1, 2, 3, 4, 5]

vip_senders: []

allowed_folders:
  - INBOX
  - Sent
```

## Troubleshooting

### "Invalid timezone" Error

**Problem**: `ValueError: Invalid timezone: 'PST'`

**Solution**: Use IANA format:
```yaml
timezone: America/Los_Angeles  # Not 'PST'
```

### "Working hours must be HH:MM" Error

**Problem**: `ValueError: start time must be in HH:MM format`

**Solution**: Use 24-hour format with leading zeros:
```yaml
working_hours:
  start: "09:00"  # Not "9:00 AM"
```

### OAuth2 Token Expires

**Problem**: `401 Unauthorized` after some time

**Solution**: The server auto-refreshes tokens. If it fails, re-run auth setup:
```bash
docker exec -it workspace-secretary uv run python -m workspace_secretary.auth_setup --config /app/config/config.yaml
```

---

**Next**: Learn [Agent Patterns](./agents) for building intelligent workflows.
