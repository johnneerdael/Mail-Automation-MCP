"""Triage tools for the LangGraph assistant.

Smart email classification using pattern matching, signals, and LLM.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

from langchain_core.tools import tool

from workspace_secretary.assistant.context import get_context
from workspace_secretary.classifier import (
    CATEGORY_ACTIONS,
    CATEGORY_LABELS,
    EmailCategory,
    prioritize_emails,
    triage_emails,
)
from workspace_secretary.db.queries import emails as email_queries

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@tool
def prioritize_inbox(
    folder: str = "INBOX",
    limit: int = 500,
    continuation_state: Optional[str] = None,
) -> str:
    """Fast pattern-based prioritization of inbox emails (NO LLM).

    Processes ALL unread emails using pattern matching and signal analysis.
    High-confidence items get labeled immediately. Unclear items get
    Secretary/Unclear label for later LLM triage.

    Run this FIRST before triage_inbox. Handles bulk email efficiently.

    Args:
        folder: Email folder to prioritize (default: INBOX)
        limit: Max emails per batch (default: 500)
        continuation_state: State from previous call for pagination

    Returns:
        JSON with prioritization results and job_id for label application
    """
    ctx = get_context()

    offset = 0
    if continuation_state:
        try:
            state = json.loads(continuation_state)
            offset = state.get("offset", 0)
        except json.JSONDecodeError:
            pass

    emails = email_queries.get_inbox_emails(
        ctx.db,
        folder=folder,
        unread_only=False,
        limit=limit,
        offset=offset,
    )

    if not emails:
        return json.dumps({
            "status": "complete",
            "message": "No emails to prioritize",
            "total_processed": 0,
        })

    result = prioritize_emails(
        emails=emails,
        user_email=ctx.user_email,
        user_name=ctx.user_name,
        vip_senders=ctx.vip_senders,
    )

    from workspace_secretary.db.queries import imap_jobs as imap_jobs_q

    all_items = []
    for cat_key, classifications in result.by_category.items():
        for c in classifications:
            all_items.append(c.to_dict())

    job_id = None
    if all_items:
        payload = {
            "items": all_items,
            "auto_apply_high_confidence": True,
        }
        job_id = imap_jobs_q.create_job(ctx.db, job_type="triage_apply", payload=payload)
        imap_jobs_q.append_event(ctx.db, job_id, f"Prioritize job queued: {len(all_items)} items")

    total_in_folder = email_queries.count_emails(ctx.db, folder)
    has_more = (offset + len(emails)) < total_in_folder

    return json.dumps({
        "status": "partial" if has_more else "complete",
        "has_more": has_more,
        "continuation_state": json.dumps({"offset": offset + len(emails)}) if has_more else None,
        "job_id": job_id,
        "total_processed": result.total_processed,
        "high_confidence_count": len(result.high_confidence),
        "needs_review_count": len(result.needs_review),
        "summary": {cat: len(items) for cat, items in result.by_category.items()},
    })


@tool
async def triage_inbox(
    folder: str = "INBOX",
    limit: int = 100,
    continuation_state: Optional[str] = None,
) -> str:
    """LLM-assisted triage for emails marked Secretary/Unclear.

    Run prioritize_inbox FIRST to label high-confidence emails.
    This tool processes ONLY emails with Secretary/Unclear label,
    sending them to LLM for deeper classification.

    Args:
        folder: Email folder to triage (default: INBOX)
        limit: Max emails per batch (default: 100)
        continuation_state: State from previous call for pagination

    Returns:
        JSON with triage results grouped by category and confidence
    """
    ctx = get_context()

    offset = 0
    if continuation_state:
        try:
            state = json.loads(continuation_state)
            offset = state.get("offset", 0)
        except json.JSONDecodeError:
            pass

    emails = email_queries.get_emails_by_label(
        ctx.db,
        label="Secretary/Unclear",
        folder=folder,
        limit=limit,
        offset=offset,
    )

    if not emails:
        return json.dumps({
            "status": "complete",
            "message": "No unclear emails to triage. Run prioritize_inbox first.",
            "total_processed": 0,
        })

    from workspace_secretary.assistant.graph import create_llm

    llm_client = create_llm(ctx.config)

    result = await triage_emails(
        emails=emails,
        llm_client=llm_client,
        user_email=ctx.user_email,
        user_name=ctx.user_name,
        vip_senders=ctx.vip_senders,
    )

    from workspace_secretary.db.queries import imap_jobs as imap_jobs_q

    all_items = []
    for cat_key, classifications in result.by_category.items():
        for c in classifications:
            item = c.to_dict()
            item["remove_label"] = "Secretary/Unclear"
            all_items.append(item)

    job_id = None
    if all_items:
        payload = {
            "items": all_items,
            "auto_apply_high_confidence": True,
        }
        job_id = imap_jobs_q.create_job(ctx.db, job_type="triage_apply", payload=payload)
        imap_jobs_q.append_event(ctx.db, job_id, f"Triage job queued: {len(all_items)} items")

    unclear_count = email_queries.count_emails_by_label(ctx.db, "Secretary/Unclear", folder)
    has_more = (offset + len(emails)) < unclear_count

    return json.dumps({
        "status": "partial" if has_more else "complete",
        "has_more": has_more,
        "continuation_state": json.dumps({"offset": offset + len(emails)}) if has_more else None,
        "job_id": job_id,
        **result.to_dict(),
    })


@tool
def apply_triage_labels(
    classifications_json: str,
    auto_apply_high_confidence: bool = True,
) -> str:
    """Apply labels and actions from triage results.

    For high-confidence (>90%) classifications:
    - Auto-applies labels
    - Marks read if specified in actions
    - Archives if specified in actions

    For lower confidence, applies labels but skips destructive actions
    unless explicitly approved.

    Args:
        classifications_json: JSON array of classification results from triage_inbox
        auto_apply_high_confidence: If True, auto-apply all high confidence actions

    Returns:
        JSON with job_id for tracking progress
    """
    ctx = get_context()

    try:
        items = json.loads(classifications_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid classifications JSON"})

    if not items:
        return json.dumps({"error": "No items to process", "count": 0})

    job_items = []
    for item in items:
        uid = item.get("uid")
        if not uid:
            continue
        job_items.append({
            "uid": uid,
            "folder": item.get("folder", "INBOX"),
            "label": item.get("label"),
            "actions": item.get("actions", []),
            "confidence": item.get("confidence", 0),
        })

    if not job_items:
        return json.dumps({"error": "No valid items to process", "count": 0})

    from workspace_secretary.db.queries import imap_jobs as imap_jobs_q

    payload = {
        "items": job_items,
        "auto_apply_high_confidence": auto_apply_high_confidence,
    }
    job_id = imap_jobs_q.create_job(ctx.db, job_type="triage_apply", payload=payload)
    imap_jobs_q.append_event(ctx.db, job_id, f"Triage apply job queued: {len(job_items)} items")

    return json.dumps({
        "job_id": job_id,
        "status": "pending",
        "count": len(job_items),
        "message": f"Queued {len(job_items)} emails for label application. Job ID: {job_id}",
    })


@tool
def get_triage_summary(classifications_json: str) -> str:
    """Format triage results for user display.

    Takes raw triage results and formats them for human review,
    showing counts by category and sample emails.

    Args:
        classifications_json: JSON with triage results from triage_inbox

    Returns:
        Formatted markdown summary for display
    """
    try:
        data = json.loads(classifications_json)
    except json.JSONDecodeError:
        return "Error: Invalid triage data"

    lines = [f"## Inbox Triage Results\n"]
    lines.append(f"**Total processed:** {data.get('total_processed', 0)} emails\n")

    summary = data.get("summary", {})
    high_conf_count = data.get("high_confidence_count", 0)
    review_count = data.get("needs_review_count", 0)

    lines.append(f"**High confidence (auto-apply):** {high_conf_count}")
    lines.append(f"**Needs review:** {review_count}\n")

    category_icons = {
        "action-required": "🔴",
        "fyi": "📋",
        "newsletter": "📰",
        "notification": "🔔",
        "cleanup": "🗑️",
        "unclear": "❓",
    }

    category_labels = {
        "action-required": "Action Required",
        "fyi": "FYI / Informational",
        "newsletter": "Newsletters",
        "notification": "Notifications",
        "cleanup": "Safe to Archive",
        "unclear": "Needs Review",
    }

    by_category = data.get("by_category", {})

    for cat_key in [
        "action-required",
        "fyi",
        "newsletter",
        "notification",
        "cleanup",
        "unclear",
    ]:
        items = by_category.get(cat_key, [])
        if not items:
            continue

        icon = category_icons.get(cat_key, "📧")
        label = category_labels.get(cat_key, cat_key)
        count = len(items)

        lines.append(f"\n### {icon} {label} ({count})")

        for item in items[:5]:
            uid = item.get("uid")
            reasoning = item.get("reasoning", "")
            confidence = item.get("confidence", 0)
            conf_pct = int(confidence * 100)
            lines.append(f"- UID {uid}: {reasoning} ({conf_pct}%)")

        if count > 5:
            lines.append(f"- ... and {count - 5} more")

    return "\n".join(lines)


TRIAGE_TOOLS = [triage_inbox, apply_triage_labels, get_triage_summary]
