"""
Base PostgreSQL database implementation.

Provides connection pooling, schema initialization, and abstract interface.
Engine extends this with self-healing embeddings logic.
Web imports this directly for read-only operations.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from workspace_secretary.db.types import DatabaseInterface
from workspace_secretary.db import schema


class PostgresDatabase(DatabaseInterface):
    """
    Base PostgreSQL database with connection pooling and schema initialization.

    This is the shared implementation used by both engine and web.
    Engine extends this with self-healing embeddings logic.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "secretary",
        user: str = "secretary",
        password: str = "",
        ssl_mode: str = "prefer",
        embedding_dimensions: int = 1536,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.ssl_mode = ssl_mode
        self.embedding_dimensions = embedding_dimensions
        self._pool: Any = None
        self._vector_type = "halfvec" if embedding_dimensions > 2000 else "vector"
        self._vector_ops = (
            "halfvec_ip_ops" if embedding_dimensions > 2000 else "vector_ip_ops"
        )

    def supports_embeddings(self) -> bool:
        """PostgreSQL with pgvector always supports embeddings."""
        return True

    def _get_connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"

    def initialize(self) -> None:
        """
        Initialize connection pool and create all schemas.

        Calls idempotent schema functions from workspace_secretary.db.schema.
        Subclasses (like EnginePostgresDatabase) can override to add self-healing logic.
        """
        try:
            from psycopg_pool import ConnectionPool
        except ImportError:
            raise ImportError(
                "PostgreSQL support requires psycopg[binary] and psycopg_pool. "
                "Install with: pip install 'psycopg[binary]' psycopg_pool"
            )

        self._pool = ConnectionPool(
            self._get_connection_string(), min_size=1, max_size=10
        )

        # Initialize all schemas using shared schema module
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                schema.initialize_core_schema(
                    cur, self._vector_type, self.embedding_dimensions
                )
                schema.initialize_embeddings_schema(
                    cur, self._vector_type, self.embedding_dimensions
                )
                schema.initialize_contacts_schema(cur)
                schema.initialize_calendar_schema(cur)
                schema.initialize_mutation_journal(cur)
                schema.create_indexes(cur, self._vector_type)
                conn.commit()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """
        Context manager for database connections.

        Yields a psycopg connection from the pool.
        """
        if not self._pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        with self._pool.connection() as conn:
            yield conn

    def close(self) -> None:
        """Close connection pool and release resources."""
        if self._pool:
            self._pool.close()
            self._pool = None

    # All CRUD methods intentionally NOT implemented here yet.
    # They remain in workspace_secretary.engine.database.PostgresDatabase for now.
    # Future PRs will extract them to workspace_secretary.db.queries modules.

    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def upsert_user_preferences(self, user_id: str, prefs: dict[str, Any]) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def ensure_calendar_schema(self) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def upsert_calendar_sync_state(
        self,
        calendar_id: str,
        window_start: str,
        window_end: str,
        sync_token: str | None,
        status: str = "ok",
        last_error: str | None = None,
        last_full_sync_at: str | None = None,
        last_incremental_sync_at: str | None = None,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_calendar_sync_state(self, calendar_id: str) -> dict[str, Any] | None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def list_calendar_sync_states(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def upsert_calendar_event_cache(
        self,
        calendar_id: str,
        event_id: str,
        raw_json: dict[str, Any],
        etag: str | None = None,
        updated: str | None = None,
        status: str | None = None,
        start_ts_utc: str | None = None,
        end_ts_utc: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        is_all_day: bool = False,
        summary: str | None = None,
        location: str | None = None,
        local_status: str = "synced",
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def delete_calendar_event_cache(self, calendar_id: str, event_id: str) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def query_calendar_events_cached(
        self,
        calendar_ids: list[str],
        time_min: str,
        time_max: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def enqueue_calendar_outbox(
        self,
        op_type: str,
        calendar_id: str,
        payload_json: dict[str, Any],
        event_id: str | None = None,
        local_temp_id: str | None = None,
    ) -> str:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def list_calendar_outbox(
        self, statuses: list[str] | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def update_calendar_outbox_status(
        self,
        outbox_id: str,
        status: str,
        error: str | None = None,
        event_id: str | None = None,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_synced_uids(self, folder: str) -> list[int]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def count_emails(self, folder: str) -> int:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def upsert_embedding(
        self,
        uid: int,
        folder: str,
        embedding: list[float],
        model: str,
        content_hash: str,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_synced_folders(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_thread_emails(
        self, uid: int, folder: str = "INBOX"
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def semantic_search(
        self,
        query_embedding: list[float],
        folder: str = "INBOX",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def semantic_search_filtered(
        self,
        query_embedding: list[float],
        folder: str | None = None,
        from_addr: str | None = None,
        to_addr: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        has_attachments: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def find_similar_emails(
        self, uid: int, folder: str = "INBOX", limit: int = 5
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def upsert_email(
        self,
        uid: int,
        folder: str,
        message_id: str | None,
        subject: str | None,
        from_addr: str,
        to_addr: str,
        cc_addr: str,
        bcc_addr: str,
        date: str | None,
        internal_date: str | None,
        body_text: str,
        body_html: str,
        flags: str,
        is_unread: bool,
        is_important: bool,
        size: int,
        modseq: int,
        in_reply_to: str,
        references_header: str,
        gmail_thread_id: int | None,
        gmail_msgid: int | None,
        gmail_labels: list[str] | None,
        has_attachments: bool,
        attachment_filenames: list[str] | None,
        auth_results_raw: str | None = None,
        spf: str | None = None,
        dkim: str | None = None,
        dmarc: str | None = None,
        is_suspicious_sender: bool = False,
        suspicious_sender_signals: dict[str, Any] | None = None,
        security_score: int = 100,
        warning_type: str | None = None,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def update_email_flags(
        self,
        uid: int,
        folder: str,
        flags: str,
        is_unread: bool,
        modseq: int,
        gmail_labels: list[str] | None = None,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_email_by_uid(self, uid: int, folder: str) -> dict[str, Any] | None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_emails_by_uids(self, uids: list[int], folder: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def search_emails(
        self,
        folder: str = "INBOX",
        is_unread: bool | None = None,
        from_addr: str | None = None,
        to_addr: str | None = None,
        subject_contains: str | None = None,
        body_contains: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def delete_email(self, uid: int, folder: str) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def mark_email_read(self, uid: int, folder: str, is_read: bool) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_folder_state(self, folder: str) -> dict[str, Any] | None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def save_folder_state(
        self, folder: str, uidvalidity: int, uidnext: int, highestmodseq: int = 0
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def clear_folder(self, folder: str) -> int:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def log_sync_error(
        self,
        error_type: str,
        error_message: str,
        folder: str | None = None,
        email_uid: int | None = None,
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def create_mutation(
        self,
        email_uid: int,
        email_folder: str,
        action: str,
        params: dict | None = None,
        pre_state: dict | None = None,
    ) -> int:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def update_mutation_status(
        self, mutation_id: int, status: str, error: str | None = None
    ) -> None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_pending_mutations(self, email_uid: int, email_folder: str) -> list[dict]:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )

    def get_mutation(self, mutation_id: int) -> dict | None:
        raise NotImplementedError(
            "CRUD methods not yet extracted to base. Use engine.database for now."
        )
