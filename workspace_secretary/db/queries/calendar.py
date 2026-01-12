"""Calendar query functions for sync state, events cache, and offline outbox."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from psycopg.rows import dict_row

from workspace_secretary.db.types import DatabaseInterface


def upsert_calendar_sync_state(
    db: DatabaseInterface,
    calendar_id: str,
    window_start: str,
    window_end: str,
    sync_token: Optional[str],
    status: str = "ok",
    last_error: Optional[str] = None,
    last_full_sync_at: Optional[str] = None,
    last_incremental_sync_at: Optional[str] = None,
) -> None:
    """Insert or update calendar sync state."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_sync_state (
                    calendar_id, sync_token, window_start, window_end,
                    last_full_sync_at, last_incremental_sync_at, status, last_error
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(calendar_id) DO UPDATE SET
                    sync_token = EXCLUDED.sync_token,
                    window_start = EXCLUDED.window_start,
                    window_end = EXCLUDED.window_end,
                    last_full_sync_at = COALESCE(EXCLUDED.last_full_sync_at, calendar_sync_state.last_full_sync_at),
                    last_incremental_sync_at = COALESCE(EXCLUDED.last_incremental_sync_at, calendar_sync_state.last_incremental_sync_at),
                    status = EXCLUDED.status,
                    last_error = EXCLUDED.last_error
                """,
                (
                    calendar_id,
                    sync_token,
                    window_start,
                    window_end,
                    last_full_sync_at,
                    last_incremental_sync_at,
                    status,
                    last_error,
                ),
            )
            conn.commit()


def get_calendar_sync_state(
    db: DatabaseInterface,
    calendar_id: str,
) -> Optional[dict[str, Any]]:
    """Get sync state for calendar."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM calendar_sync_state WHERE calendar_id = %s",
                (calendar_id,),
            )
            return cur.fetchone()


def list_calendar_sync_states(
    db: DatabaseInterface,
) -> list[dict[str, Any]]:
    """List all calendar sync states."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM calendar_sync_state")
            return cur.fetchall()


def upsert_calendar_event_cache(
    db: DatabaseInterface,
    calendar_id: str,
    event_id: str,
    raw_json: dict[str, Any],
    etag: Optional[str] = None,
    updated: Optional[str] = None,
    status: Optional[str] = None,
    start_ts_utc: Optional[str] = None,
    end_ts_utc: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_all_day: bool = False,
    summary: Optional[str] = None,
    location: Optional[str] = None,
    local_status: str = "synced",
) -> None:
    """Insert or update calendar event in cache."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_events_cache (
                    calendar_id, event_id, etag, updated, status,
                    start_ts_utc, end_ts_utc, start_date, end_date, is_all_day,
                    summary, location, local_status, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(calendar_id, event_id) DO UPDATE SET
                    etag = EXCLUDED.etag,
                    updated = EXCLUDED.updated,
                    status = EXCLUDED.status,
                    start_ts_utc = EXCLUDED.start_ts_utc,
                    end_ts_utc = EXCLUDED.end_ts_utc,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    is_all_day = EXCLUDED.is_all_day,
                    summary = EXCLUDED.summary,
                    location = EXCLUDED.location,
                    local_status = EXCLUDED.local_status,
                    raw_json = EXCLUDED.raw_json
                """,
                (
                    calendar_id,
                    event_id,
                    etag,
                    updated,
                    status,
                    start_ts_utc,
                    end_ts_utc,
                    start_date,
                    end_date,
                    is_all_day,
                    summary,
                    location,
                    local_status,
                    json.dumps(raw_json),
                ),
            )
            conn.commit()


def delete_calendar_event_cache(
    db: DatabaseInterface,
    calendar_id: str,
    event_id: str,
) -> None:
    """Delete cached calendar event."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM calendar_events_cache WHERE calendar_id = %s AND event_id = %s",
                (calendar_id, event_id),
            )
            conn.commit()


def query_calendar_events_cached(
    db: DatabaseInterface,
    calendar_ids: list[str],
    time_min: str,
    time_max: str,
) -> list[dict[str, Any]]:
    """Query cached calendar events in time range."""
    if not calendar_ids:
        return []

    query = """
        SELECT raw_json, local_status
        FROM calendar_events_cache
        WHERE calendar_id = ANY(%s)
          AND (
            (is_all_day = FALSE AND start_ts_utc < %s AND end_ts_utc > %s)
            OR
            (is_all_day = TRUE AND start_date < %s::date AND end_date > %s::date)
          )
        ORDER BY COALESCE(start_ts_utc, start_date::timestamp) ASC
    """

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (calendar_ids, time_max, time_min, time_max, time_min),
            )
            results: list[dict[str, Any]] = []
            for row in cur.fetchall():
                evt = row[0]
                if isinstance(evt, str):
                    try:
                        evt = json.loads(evt)
                    except Exception:
                        continue
                evt["_local_status"] = row[1]
                results.append(evt)
            return results


def enqueue_calendar_outbox(
    db: DatabaseInterface,
    op_type: str,
    calendar_id: str,
    payload_json: dict[str, Any],
    event_id: Optional[str] = None,
    local_temp_id: Optional[str] = None,
) -> str:
    """Enqueue offline calendar operation, return outbox ID."""
    outbox_id = str(uuid.uuid4())
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_outbox (id, op_type, calendar_id, event_id, local_temp_id, payload_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    outbox_id,
                    op_type,
                    calendar_id,
                    event_id,
                    local_temp_id,
                    json.dumps(payload_json),
                ),
            )
            conn.commit()
    return outbox_id


def list_calendar_outbox(
    db: DatabaseInterface,
    statuses: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """List calendar outbox entries, optionally filtered by status."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if statuses:
                cur.execute(
                    "SELECT * FROM calendar_outbox WHERE status = ANY(%s) ORDER BY created_at",
                    (statuses,),
                )
            else:
                cur.execute("SELECT * FROM calendar_outbox ORDER BY created_at")
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r.get("payload_json"), str):
                    try:
                        r["payload_json"] = json.loads(r["payload_json"])
                    except Exception:
                        r["payload_json"] = {}
            return rows


def update_calendar_outbox_status(
    db: DatabaseInterface,
    outbox_id: str,
    status: str,
    error: Optional[str] = None,
    event_id: Optional[str] = None,
) -> None:
    """Update calendar outbox entry status."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE calendar_outbox
                SET status = %s, error = %s, event_id = COALESCE(%s, event_id),
                    attempt_count = attempt_count + 1,
                    last_attempt_at = NOW()
                WHERE id = %s
                """,
                (status, error, event_id, outbox_id),
            )
            conn.commit()
