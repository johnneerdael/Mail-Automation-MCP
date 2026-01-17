from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timezone
import logging

from workspace_secretary.web import database as db
from workspace_secretary.web import engine_client as engine
from workspace_secretary.web import templates, get_template_context
from workspace_secretary.web.routes.analysis import analyze_signals, compute_priority
from workspace_secretary.web.auth import require_auth, Session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse, name="dashboard")
async def dashboard(request: Request, session: Session = Depends(require_auth)):
    unread_emails = db.get_inbox_emails("INBOX", limit=50, offset=0, unread_only=True)

    priority_emails = []
    for email in unread_emails[:20]:
        signals = analyze_signals(email)
        priority, reason = compute_priority(signals)
        if priority in ("high", "medium"):
            priority_emails.append(
                {
                    **email,
                    "priority": priority,
                    "priority_reason": reason,
                    "signals": signals,
                }
            )

    priority_emails = sorted(
        priority_emails,
        key=lambda x: (0 if x["priority"] == "high" else 1, x.get("date", "")),
        reverse=True,
    )[:10]

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    selection_state = {"selected_ids": ["primary"], "available_ids": []}
    upcoming_events: list[dict] = []

    try:
        selection_state, events = db.get_user_calendar_events_with_state(
            session.user_id, today_start, today_end
        )
        for event in events:
            event_data = event.copy() if isinstance(event, dict) else dict(event)
            event_data["calendarId"] = event_data.get("calendarId")
            start = event_data.get("start", {}).get("dateTime", "")
            if not start:
                continue
            try:
                event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                event_time = (
                    event_time
                    if event_time.tzinfo
                    else event_time.replace(tzinfo=timezone.utc)
                )
                if event_time >= now:
                    upcoming_events.append(event_data)
            except ValueError:
                upcoming_events.append(event_data)
    except Exception as e:
        logger.error(f"Failed to load calendar events for dashboard: {e}")

    meetings_today = len(upcoming_events)
    upcoming_events = upcoming_events[:5]

    unread_count = len(unread_emails)
    priority_count = len([e for e in priority_emails if e["priority"] == "high"])

    stats = {
        "unread_count": unread_count,
        "priority_count": priority_count,
        "meetings_today": meetings_today,
    }

    return templates.TemplateResponse(
        "dashboard.html",
        get_template_context(
            request,
            priority_emails=priority_emails,
            upcoming_events=upcoming_events,
            stats=stats,
            unread_count=unread_count,
            priority_count=priority_count,
            meetings_today=meetings_today,
            now=now,
            selected_calendar_ids=selection_state.get("selected_ids", []),
        ),
    )


@router.get("/api/stats", response_class=HTMLResponse)
async def get_stats(request: Request, session: Session = Depends(require_auth)):
    unread_emails = db.get_inbox_emails("INBOX", limit=100, offset=0, unread_only=True)

    high_priority = 0
    for email in unread_emails[:30]:
        signals = analyze_signals(email)
        priority, _ = compute_priority(signals)
        if priority == "high":
            high_priority += 1

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    try:
        selection_state, events = db.get_user_calendar_events_with_state(
            session.user_id, today_start, today_end
        )
        meetings_today = len(events)
    except Exception:
        meetings_today = 0

    return templates.TemplateResponse(
        "partials/stats_badges.html",
        get_template_context(
            request,
            unread_count=len(unread_emails),
            priority_count=high_priority,
            meetings_today=meetings_today,
        ),
    )
