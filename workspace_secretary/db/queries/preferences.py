from __future__ import annotations

import json
from typing import Any

from workspace_secretary.db.types import DatabaseInterface


def get_user_preferences(db: DatabaseInterface, user_id: str) -> dict[str, Any]:
    """Get user preferences from database."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prefs_json FROM user_preferences WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {}
            try:
                return json.loads(row[0]) if row[0] else {}
            except Exception:
                return {}


def upsert_user_preferences(
    db: DatabaseInterface, user_id: str, prefs: dict[str, Any]
) -> None:
    """Insert or update user preferences."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, prefs_json, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT(user_id) DO UPDATE SET
                    prefs_json = EXCLUDED.prefs_json,
                    updated_at = NOW()
                """,
                (user_id, json.dumps(prefs)),
            )
            conn.commit()
