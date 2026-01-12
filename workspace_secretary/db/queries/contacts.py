"""Contact management query functions."""

from __future__ import annotations

from typing import Any, Optional

from psycopg import sql
from psycopg.rows import dict_row

from workspace_secretary.db.types import DatabaseInterface


def upsert_contact(
    db: DatabaseInterface,
    email: str,
    display_name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization: Optional[str] = None,
) -> Optional[int]:
    """Create or update contact, return contact ID."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contacts (email, display_name, first_name, last_name, organization, first_email_date, email_count)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 1)
                ON CONFLICT (email) DO UPDATE SET
                    display_name = COALESCE(EXCLUDED.display_name, contacts.display_name),
                    first_name = COALESCE(EXCLUDED.first_name, contacts.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, contacts.last_name),
                    organization = COALESCE(EXCLUDED.organization, contacts.organization),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (email, display_name, first_name, last_name, organization),
            )
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None


def add_contact_interaction(
    db: DatabaseInterface,
    contact_id: int,
    email_uid: int,
    email_folder: str,
    direction: str,
    subject: str,
    email_date: str,
    message_id: Optional[str] = None,
) -> None:
    """Record interaction with contact and update stats."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_interactions (contact_id, email_uid, email_folder, direction, subject, email_date, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (contact_id, email_uid, email_folder, direction) DO NOTHING
                """,
                (
                    contact_id,
                    email_uid,
                    email_folder,
                    direction,
                    subject,
                    email_date,
                    message_id,
                ),
            )
            cur.execute(
                """
                UPDATE contacts 
                SET email_count = email_count + 1,
                    last_email_date = GREATEST(COALESCE(last_email_date, %s), %s),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (email_date, email_date, contact_id),
            )
            conn.commit()


def get_all_contacts(
    db: DatabaseInterface,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    sort_by: str = "last_email_date",
) -> list[dict[str, Any]]:
    """Get all contacts with pagination, search, and sorting."""
    valid_sorts = ["last_email_date", "email_count", "email", "display_name"]
    if sort_by not in valid_sorts:
        sort_by = "last_email_date"

    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if search:
                query = sql.SQL(
                    """
                    SELECT id, email, display_name, first_name, last_name, organization,
                           email_count, last_email_date, first_email_date, is_vip, is_internal
                    FROM contacts
                    WHERE search_vector @@ plainto_tsquery('english', %s)
                       OR email ILIKE %s
                    ORDER BY {} DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """
                ).format(sql.Identifier(sort_by))
                cur.execute(query, (search, f"%{search}%", limit, offset))
            else:
                query = sql.SQL(
                    """
                    SELECT id, email, display_name, first_name, last_name, organization,
                           email_count, last_email_date, first_email_date, is_vip, is_internal
                    FROM contacts
                    ORDER BY {} DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """
                ).format(sql.Identifier(sort_by))
                cur.execute(query, (limit, offset))
            return cur.fetchall()


def get_contact_by_email(
    db: DatabaseInterface,
    email: str,
) -> Optional[dict[str, Any]]:
    """Get contact details by email address."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, email, display_name, first_name, last_name, organization,
                       email_count, last_email_date, first_email_date, is_vip, is_internal
                FROM contacts
                WHERE email = %s
                """,
                (email,),
            )
            return cur.fetchone()


def get_contact_interactions(
    db: DatabaseInterface,
    contact_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get recent interactions with contact."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, email_uid, email_folder, direction, subject, email_date, message_id
                FROM contact_interactions
                WHERE contact_id = %s
                ORDER BY email_date DESC
                LIMIT %s
                """,
                (contact_id, limit),
            )
            return cur.fetchall()


def get_frequent_contacts(
    db: DatabaseInterface,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get most frequently contacted people."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, email, display_name, email_count, last_email_date
                FROM contacts
                ORDER BY email_count DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def get_recent_contacts(
    db: DatabaseInterface,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get recently contacted people."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, email, display_name, email_count, last_email_date
                FROM contacts
                WHERE last_email_date IS NOT NULL
                ORDER BY last_email_date DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def search_contacts_autocomplete(
    db: DatabaseInterface,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search contacts for autocomplete."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT email, display_name, email_count
                FROM contacts
                WHERE email ILIKE %s OR display_name ILIKE %s
                ORDER BY email_count DESC
                LIMIT %s
                """,
                (f"%{query}%", f"%{query}%", limit),
            )
            return cur.fetchall()


def update_contact_vip_status(
    db: DatabaseInterface,
    contact_id: int,
    is_vip: bool,
) -> None:
    """Toggle VIP status for contact."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE contacts SET is_vip = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (is_vip, contact_id),
            )
            conn.commit()


def add_contact_note(
    db: DatabaseInterface,
    contact_id: int,
    note: str,
) -> Optional[int]:
    """Add note to contact, return note ID."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO contact_notes (contact_id, note) VALUES (%s, %s) RETURNING id",
                (contact_id, note),
            )
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None


def get_contact_notes(
    db: DatabaseInterface,
    contact_id: int,
) -> list[dict[str, Any]]:
    """Get all notes for contact."""
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, note, created_at, updated_at
                FROM contact_notes
                WHERE contact_id = %s
                ORDER BY created_at DESC
                """,
                (contact_id,),
            )
            return cur.fetchall()
