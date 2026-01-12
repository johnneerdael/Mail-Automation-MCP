"""
Database interface types and protocols.

Moved from workspace_secretary.engine.database to enable shared usage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Protocol


class DatabaseConnection(Protocol):
    """Protocol for database connection objects."""

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...
    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> Any: ...
    def fetchone(self) -> Optional[dict[str, Any]]: ...
    def fetchall(self) -> list[dict[str, Any]]: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


class DatabaseInterface(ABC):
    """Abstract interface for database operations."""

    @abstractmethod
    def supports_embeddings(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    @contextmanager
    def connection(self) -> Iterator[Any]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def upsert_user_preferences(self, user_id: str, prefs: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def ensure_calendar_schema(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_calendar_sync_state(
        self,
        calendar_id: str,
        window_start: str,
        window_end: str,
        sync_token: Optional[str],
        status: str = "ok",
        last_error: Optional[str] = None,
        last_full_sync_at: Optional[str] = None,
        last_incremental_sync_at: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_calendar_sync_state(self, calendar_id: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_calendar_sync_states(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def upsert_calendar_event_cache(
        self,
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
        raise NotImplementedError

    @abstractmethod
    def delete_calendar_event_cache(self, calendar_id: str, event_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def query_calendar_events_cached(
        self,
        calendar_ids: list[str],
        time_min: str,
        time_max: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def enqueue_calendar_outbox(
        self,
        op_type: str,
        calendar_id: str,
        payload_json: dict[str, Any],
        event_id: Optional[str] = None,
        local_temp_id: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_calendar_outbox(
        self, statuses: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def update_calendar_outbox_status(
        self,
        outbox_id: str,
        status: str,
        error: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_synced_uids(self, folder: str) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def count_emails(self, folder: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def upsert_embedding(
        self,
        uid: int,
        folder: str,
        embedding: list[float],
        model: str,
        content_hash: str,
    ) -> None:
        raise NotImplementedError

    def get_synced_folders(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_thread_emails(
        self, uid: int, folder: str = "INBOX"
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def semantic_search(
        self,
        query_embedding: list[float],
        folder: str = "INBOX",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def semantic_search_filtered(
        self,
        query_embedding: list[float],
        folder: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def find_similar_emails(
        self, uid: int, folder: str = "INBOX", limit: int = 5
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def upsert_email(
        self,
        uid: int,
        folder: str,
        message_id: Optional[str],
        subject: Optional[str],
        from_addr: str,
        to_addr: str,
        cc_addr: str,
        bcc_addr: str,
        date: Optional[str],
        internal_date: Optional[str],
        body_text: str,
        body_html: str,
        flags: str,
        is_unread: bool,
        is_important: bool,
        size: int,
        modseq: int,
        in_reply_to: str,
        references_header: str,
        gmail_thread_id: Optional[int],
        gmail_msgid: Optional[int],
        gmail_labels: Optional[list[str]],
        has_attachments: bool,
        attachment_filenames: Optional[list[str]],
        auth_results_raw: Optional[str] = None,
        spf: Optional[str] = None,
        dkim: Optional[str] = None,
        dmarc: Optional[str] = None,
        is_suspicious_sender: bool = False,
        suspicious_sender_signals: Optional[dict[str, Any]] = None,
        security_score: int = 100,
        warning_type: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_email_flags(
        self,
        uid: int,
        folder: str,
        flags: str,
        is_unread: bool,
        modseq: int,
        gmail_labels: Optional[list[str]] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_email_by_uid(self, uid: int, folder: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_emails_by_uids(self, uids: list[int], folder: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def search_emails(
        self,
        folder: str = "INBOX",
        is_unread: Optional[bool] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        subject_contains: Optional[str] = None,
        body_contains: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete_email(self, uid: int, folder: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_email_read(self, uid: int, folder: str, is_read: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_folder_state(self, folder: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_folder_state(
        self, folder: str, uidvalidity: int, uidnext: int, highestmodseq: int = 0
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear_folder(self, folder: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def log_sync_error(
        self,
        error_type: str,
        error_message: str,
        folder: Optional[str] = None,
        email_uid: Optional[int] = None,
    ) -> None:
        raise NotImplementedError

    def create_mutation(
        self,
        email_uid: int,
        email_folder: str,
        action: str,
        params: Optional[dict] = None,
        pre_state: Optional[dict] = None,
    ) -> int:
        raise NotImplementedError

    def update_mutation_status(
        self, mutation_id: int, status: str, error: Optional[str] = None
    ) -> None:
        raise NotImplementedError

    def get_pending_mutations(self, email_uid: int, email_folder: str) -> list[dict]:
        raise NotImplementedError

    def get_mutation(self, mutation_id: int) -> Optional[dict]:
        raise NotImplementedError
