from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from workspace_secretary.db.types import DatabaseInterface


def create_job(db: DatabaseInterface, job_type: str, payload: dict[str, Any] | None = None) -> str:
    job_id = str(uuid.uuid4())
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO imap_jobs (job_id, job_type, status, payload)
                VALUES (%s, %s, 'pending', %s)
                """,
                (job_id, job_type, json.dumps(payload) if payload else None),
            )
            conn.commit()
    return job_id


def get_job(db: DatabaseInterface, job_id: str) -> Optional[dict[str, Any]]:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM imap_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))


def request_cancel(db: DatabaseInterface, job_id: str) -> bool:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE imap_jobs
                SET cancel_requested = TRUE
                WHERE job_id = %s
                  AND status IN ('pending', 'running')
                """,
                (job_id,),
            )
            updated = cur.rowcount
            conn.commit()
            return updated > 0


def append_event(
    db: DatabaseInterface,
    job_id: str,
    message: str,
    *,
    level: str = "info",
    data: Optional[dict[str, Any]] = None,
) -> int:
    payload = json.dumps(data or {})
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO imap_job_events (job_id, level, message, data)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (job_id, level, message, payload),
            )
            event_id = cur.fetchone()[0]
            conn.commit()
            return int(event_id)


def list_events(
    db: DatabaseInterface, job_id: str, *, after_id: int = 0, limit: int = 200
) -> list[dict[str, Any]]:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, job_id, created_at, level, message, data
                FROM imap_job_events
                WHERE job_id = %s AND id > %s
                ORDER BY id ASC
                LIMIT %s
                """,
                (job_id, after_id, limit),
            )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]


def update_progress(
    db: DatabaseInterface,
    job_id: str,
    *,
    processed: Optional[int] = None,
    total_estimate: Optional[int] = None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []

    if processed is not None:
        sets.append("processed = %s")
        params.append(processed)
    if total_estimate is not None:
        sets.append("total_estimate = %s")
        params.append(total_estimate)

    if not sets:
        return

    params.append(job_id)

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE imap_jobs SET {', '.join(sets)} WHERE job_id = %s",
                tuple(params),
            )
            conn.commit()


def mark_running(db: DatabaseInterface, job_id: str) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE imap_jobs
                SET status = 'running', started_at = NOW()
                WHERE job_id = %s AND status = 'pending'
                """,
                (job_id,),
            )
            conn.commit()


def mark_finished(
    db: DatabaseInterface, job_id: str, *, status: str, error: Optional[str] = None
) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE imap_jobs
                SET status = %s, finished_at = NOW(), error = %s
                WHERE job_id = %s
                """,
                (status, error, job_id),
            )
            conn.commit()


def claim_next_job(db: DatabaseInterface, job_type: str) -> Optional[dict[str, Any]]:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id
                FROM imap_jobs
                WHERE status = 'pending' AND job_type = %s
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (job_type,),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return None

            job_id = row[0]
            cur.execute(
                """
                UPDATE imap_jobs
                SET status = 'running', started_at = NOW()
                WHERE job_id = %s
                """,
                (job_id,),
            )
            cur.execute("SELECT * FROM imap_jobs WHERE job_id = %s", (job_id,))
            full_row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
            conn.commit()
            return dict(zip(columns, full_row))


def is_cancel_requested(db: DatabaseInterface, job_id: str) -> bool:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cancel_requested FROM imap_jobs WHERE job_id = %s", (job_id,)
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False


def insert_candidate(
    db: DatabaseInterface,
    job_id: str,
    *,
    uid: int,
    folder: str,
    message_id: Optional[str] = None,
    from_addr: Optional[str] = None,
    to_addr: Optional[str] = None,
    cc_addr: Optional[str] = None,
    subject: Optional[str] = None,
    date: Optional[Any] = None,
    body_preview: Optional[str] = None,
    category: str,
    confidence: float,
    signals: Optional[dict[str, Any]] = None,
    proposed_actions: Optional[list[str]] = None,
) -> int:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO imap_job_candidates (
                    job_id, uid, folder, message_id, from_addr, to_addr, cc_addr,
                    subject, date, body_preview, category, confidence, signals, proposed_actions
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    job_id,
                    uid,
                    folder,
                    message_id,
                    from_addr,
                    to_addr,
                    cc_addr,
                    subject,
                    date,
                    body_preview,
                    category,
                    confidence,
                    json.dumps(signals or {}),
                    json.dumps(proposed_actions or []),
                ),
            )
            cid = cur.fetchone()[0]
            conn.commit()
            return int(cid)


def list_candidates(
    db: DatabaseInterface,
    job_id: str,
    *,
    min_confidence: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    clauses = ["job_id = %s"]
    params: list[Any] = [job_id]

    if min_confidence is not None:
        clauses.append("confidence >= %s")
        params.append(min_confidence)
    if category is not None:
        clauses.append("category = %s")
        params.append(category)

    params.append(limit)

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id, job_id, uid, folder, message_id, from_addr, to_addr, cc_addr,
                    subject, date, body_preview, category, confidence, signals,
                    proposed_actions, user_decision, created_at
                FROM imap_job_candidates
                WHERE {' AND '.join(clauses)}
                ORDER BY confidence DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]


def set_candidate_decision(
    db: DatabaseInterface, candidate_id: int, decision: str
) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE imap_job_candidates SET user_decision = %s WHERE id = %s",
                (decision, candidate_id),
            )
            conn.commit()


def record_approval(
    db: DatabaseInterface,
    job_id: str,
    *,
    approved_by: str,
    approval_payload: dict[str, Any],
) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE imap_jobs
                SET approved_at = NOW(), approved_by = %s, approval_payload = %s
                WHERE job_id = %s
                """,
                (approved_by, json.dumps(approval_payload), job_id),
            )
            conn.commit()


def get_approval(db: DatabaseInterface, job_id: str) -> Optional[dict[str, Any]]:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT approved_at, approved_by, approval_payload
                FROM imap_jobs
                WHERE job_id = %s AND approved_at IS NOT NULL
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "approved_at": row[0],
                "approved_by": row[1],
                "approval_payload": row[2],
            }


def claim_next_approved_job(
    db: DatabaseInterface, job_type: str
) -> Optional[dict[str, Any]]:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id
                FROM imap_jobs
                WHERE status = 'approved' AND job_type = %s
                ORDER BY approved_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (job_type,),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return None

            job_id = row[0]
            cur.execute(
                """
                UPDATE imap_jobs
                SET status = 'executing', started_at = NOW()
                WHERE job_id = %s
                """,
                (job_id,),
            )
            cur.execute("SELECT * FROM imap_jobs WHERE job_id = %s", (job_id,))
            full_row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
            conn.commit()
            return dict(zip(columns, full_row))


def mark_approved(db: DatabaseInterface, job_id: str) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE imap_jobs
                SET status = 'approved'
                WHERE job_id = %s AND status IN ('completed', 'pending')
                """,
                (job_id,),
            )
            conn.commit()
