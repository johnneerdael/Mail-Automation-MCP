# Intelligence Tools

Smart analysis and prioritization tools.

## get_daily_briefing

Combined calendar + email intelligence for a given day.

**Parameters:**
- `date` (string, required): ISO date (YYYY-MM-DD)

**Returns:**
```json
{
  "date": "2026-01-09",
  "timezone": "America/Los_Angeles",
  "calendar_events": [...],
  "email_candidates": [
    {
      "subject": "...",
      "from": "...",
      "date": "...",
      "snippet": "...",
      "signals": {
        "is_addressed_to_me": true,
                        "mentions_my_name": false,
                        "is_from_vip": true,
        "is_important": false,
        "has_question": true,
        "mentions_deadline": false,
        "mentions_meeting": true
      }
    }
  ]
}
```

**Signals:**
- `is_addressed_to_me`: User's email is in To: field
- `mentions_my_name`: User's full name mentioned in body
- `is_from_vip`: Sender in configured `vip_senders`
- `is_important`: Gmail IMPORTANT label
- `has_question`: Contains `?` or polite requests
- `mentions_deadline`: Keywords like EOD, ASAP, urgent
- `mentions_meeting`: Keywords like meet, schedule, zoom

**AI should decide priority** based on these signals + context.

## summarize_thread

Get structured summary of email thread.

**Parameters:**
- `thread_id` (string, required): Gmail thread ID

**Returns:**
- `participants`: List of all senders/recipients
- `key_points`: Extracted discussion points
- `action_items`: Detected tasks/requests
- `latest_message`: Most recent message

## quick_clean_inbox

Automatically clean inbox by moving emails where user is not directly addressed.

**Parameters:**
- `batch_size` (number, optional): Emails per batch (default: 20)

**Returns:**
```json
{
  "status": "success",
  "total_processed": 45,
  "moved": 12,
  "skipped": 33,
  "target_folder": "Secretary/Auto-Cleaned",
  "moved_emails": [{"uid": "123", "from": "...", "subject": "..."}],
  "skipped_emails": [{"uid": "456", "from": "...", "subject": "..."}]
}
```

**Safety Guarantees:**
- Only moves emails where user is NOT in To: or CC: fields
- Only moves emails where user's email/name is NOT in body
- Emails moved to `Secretary/Auto-Cleaned` (recoverable)
- Each email checked exactly once (no loops)

::: warning UNIQUE: No Confirmation Required
This is the **only mutation tool** that does not require user confirmation per AGENTS.md. The safety conditions are deterministic—if both fail, the email is provably not directed at the user.
:::

## More Tools

See full tool list in the [README](https://github.com/johnneerdael/Google-Workspace-Secretary-MCP#-available-tools).
