from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from workspace_secretary.db.queries import imap_jobs as imap_jobs_q
from workspace_secretary.web.auth import require_auth
from workspace_secretary.web.database import get_db

router = APIRouter(prefix="/api/imap-jobs", tags=["imap-jobs"])


@router.post("/sync")
def create_sync_job(session: Any = Depends(require_auth)) -> dict[str, Any]:
    db = get_db()
    job_id = imap_jobs_q.create_job(db, job_type="sync")
    imap_jobs_q.append_event(db, job_id, "Job queued")
    return {"job_id": job_id, "status": "pending", "user_id": getattr(session, "user_id", None)}


@router.get("/{job_id}")
def get_job(job_id: str, _: Any = Depends(require_auth)) -> dict[str, Any]:
    db = get_db()
    job = imap_jobs_q.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, _: Any = Depends(require_auth)) -> dict[str, Any]:
    db = get_db()
    ok = imap_jobs_q.request_cancel(db, job_id)
    if ok:
        imap_jobs_q.append_event(db, job_id, "Cancellation requested")
    return {"ok": ok}


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.get("/{job_id}/events")
def stream_job_events(
    job_id: str,
    request: Request,
    after_id: int = 0,
    _: Any = Depends(require_auth),
) -> StreamingResponse:
    db = get_db()

    job = imap_jobs_q.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    def gen():
        last_id = after_id
        while True:
            if request.client is None:
                break

            if getattr(request, "is_disconnected", None):
                try:
                    if request.is_disconnected():
                        break
                except Exception:
                    pass

            events = imap_jobs_q.list_events(db, job_id, after_id=last_id)
            for e in events:
                last_id = int(e["id"])
                yield _sse(
                    {
                        "type": "job_event",
                        "id": e["id"],
                        "created_at": e["created_at"],
                        "level": e["level"],
                        "message": e["message"],
                        "data": e["data"],
                    }
                )

            job_row = imap_jobs_q.get_job(db, job_id)
            if job_row is None:
                yield _sse({"type": "error", "message": "Job disappeared"})
                break

            yield _sse(
                {
                    "type": "job_status",
                    "status": job_row.get("status"),
                    "processed": job_row.get("processed"),
                    "total_estimate": job_row.get("total_estimate"),
                }
            )

            if job_row.get("status") in ("completed", "failed", "cancelled"):
                break

            time.sleep(0.75)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/triage")
def create_triage_preview_job(session: Any = Depends(require_auth)) -> dict[str, Any]:
    db = get_db()
    job_id = imap_jobs_q.create_job(db, job_type="triage_preview")
    imap_jobs_q.append_event(db, job_id, "Triage preview job queued")
    return {
        "job_id": job_id,
        "status": "pending",
        "user_id": getattr(session, "user_id", None),
    }


@router.get("/{job_id}/candidates")
def get_candidates(
    job_id: str,
    min_confidence: float | None = None,
    category: str | None = None,
    limit: int = 500,
    _: Any = Depends(require_auth),
) -> dict[str, Any]:
    db = get_db()
    job = imap_jobs_q.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = imap_jobs_q.list_candidates(
        db, job_id, min_confidence=min_confidence, category=category, limit=limit
    )

    high = [c for c in candidates if c["confidence"] >= 0.90]
    medium = [c for c in candidates if 0.50 <= c["confidence"] < 0.90]
    low = [c for c in candidates if c["confidence"] < 0.50]

    return {
        "job_id": job_id,
        "job_status": job.get("status"),
        "total": len(candidates),
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
    }


from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    candidate_ids: list[int]
    actions: list[str]


@router.post("/{job_id}/approve")
def approve_job(
    job_id: str,
    body: ApprovalRequest,
    session: Any = Depends(require_auth),
) -> dict[str, Any]:
    db = get_db()
    job = imap_jobs_q.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job must be in 'completed' status to approve (current: {job.get('status')})",
        )

    if imap_jobs_q.get_approval(db, job_id) is not None:
        raise HTTPException(status_code=400, detail="Job already approved")

    user_id = getattr(session, "user_id", None) or "unknown"
    approval_payload = {
        "candidate_ids": body.candidate_ids,
        "actions": body.actions,
    }

    imap_jobs_q.record_approval(
        db, job_id, approved_by=str(user_id), approval_payload=approval_payload
    )
    imap_jobs_q.mark_approved(db, job_id)
    imap_jobs_q.append_event(
        db,
        job_id,
        f"Approved by {user_id}: {len(body.candidate_ids)} candidates",
        data=approval_payload,
    )

    return {"ok": True, "job_id": job_id, "status": "approved"}


class CleanupRequest(BaseModel):
    uids: list[dict]
    destination: str = "Secretary/Auto-Cleaned"
    mark_read: bool = True


class TriageApplyRequest(BaseModel):
    items: list[dict]
    auto_apply_high_confidence: bool = True


@router.post("/cleanup")
def create_cleanup_job(
    body: CleanupRequest,
    session: Any = Depends(require_auth),
) -> dict[str, Any]:
    db = get_db()
    payload = {
        "uids": body.uids,
        "destination": body.destination,
        "mark_read": body.mark_read,
    }
    job_id = imap_jobs_q.create_job(db, job_type="bulk_cleanup", payload=payload)
    imap_jobs_q.append_event(db, job_id, f"Bulk cleanup job queued: {len(body.uids)} emails")
    return {
        "job_id": job_id,
        "status": "pending",
        "count": len(body.uids),
        "user_id": getattr(session, "user_id", None),
    }


@router.post("/triage-apply")
def create_triage_apply_job(
    body: TriageApplyRequest,
    session: Any = Depends(require_auth),
) -> dict[str, Any]:
    db = get_db()
    payload = {
        "items": body.items,
        "auto_apply_high_confidence": body.auto_apply_high_confidence,
    }
    job_id = imap_jobs_q.create_job(db, job_type="triage_apply", payload=payload)
    imap_jobs_q.append_event(db, job_id, f"Triage apply job queued: {len(body.items)} items")
    return {
        "job_id": job_id,
        "status": "pending",
        "count": len(body.items),
        "user_id": getattr(session, "user_id", None),
    }
