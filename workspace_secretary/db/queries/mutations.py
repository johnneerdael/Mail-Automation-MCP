from __future__ import annotations

import json
from typing import Any, Optional

from workspace_secretary.db.types import DatabaseInterface


def create_mutation(
    db: DatabaseInterface,
    email_uid: int,
    email_folder: str,
    action: str,
    params: Optional[dict[str, Any]] = None,
    pre_state: Optional[dict[str, Any]] = None,
) -> int:
    """Create a new mutation journal entry."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mutation_journal (email_uid, email_folder, action, params, pre_state)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    email_uid,
                    email_folder,
                    action,
                    json.dumps(params) if params else None,
                    json.dumps(pre_state) if pre_state else None,
                ),
            )
            mutation_id = cur.fetchone()[0]
            conn.commit()
            return int(mutation_id)


def update_mutation_status(
    db: DatabaseInterface, mutation_id: int, status: str, error: Optional[str] = None
) -> None:
    """Update mutation journal entry status."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE mutation_journal
                SET status = %s, error = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (status, error, mutation_id),
            )
            conn.commit()


def get_pending_mutations(
    db: DatabaseInterface, email_uid: int, email_folder: str
) -> list[dict[str, Any]]:
    """Get all pending mutations for an email."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM mutation_journal
                WHERE email_uid = %s AND email_folder = %s AND status = 'PENDING'
                ORDER BY created_at
                """,
                (email_uid, email_folder),
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_mutation(db: DatabaseInterface, mutation_id: int) -> Optional[dict[str, Any]]:
    """Get a single mutation journal entry by ID."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mutation_journal WHERE id = %s", (mutation_id,))
            row = cur.fetchone()
            if row:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))
            return None
