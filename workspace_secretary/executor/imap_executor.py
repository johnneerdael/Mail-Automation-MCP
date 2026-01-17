from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Empty
from typing import Generator, Optional

from workspace_secretary.config import load_config_with_oauth2 as load_config
from workspace_secretary.db.postgres import PostgresDatabase
from workspace_secretary.db.queries import imap_jobs as imap_jobs_q
from workspace_secretary.db.queries import emails as email_queries
from workspace_secretary.engine import api as engine_api
from workspace_secretary.imap_client import ImapClient
from workspace_secretary.classifier import triage_emails

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutorConfig:
    max_concurrent_jobs: int = 3
    poll_interval_s: float = 1.0


@contextmanager
def get_imap_from_pool(timeout: float = 60) -> Generator[ImapClient, None, None]:
    client: Optional[ImapClient] = None
    try:
        client = engine_api.state._imap_pool.get(timeout=timeout)
        yield client
    except Empty:
        raise RuntimeError("No IMAP connections available in pool")
    finally:
        if client:
            engine_api.state._imap_pool.put(client)


async def _run_sync_job(job_id: str) -> None:
    config = load_config()

    if config.database.backend.value != "postgres":
        raise RuntimeError("imap-executor requires postgres database backend")

    db_cfg = config.database.postgres
    db = PostgresDatabase(
        host=db_cfg.host,
        port=db_cfg.port,
        database=db_cfg.database,
        user=db_cfg.user,
        password=db_cfg.password,
        ssl_mode=db_cfg.ssl_mode,
        embedding_dimensions=config.database.embeddings.dimensions,
    )
    db.initialize()

    engine_api.state.database = db

    await engine_api.sync_emails_parallel()

    imap_jobs_q.append_event(db, job_id, "Sync complete")


async def _run_triage_preview_job(job_id: str, db: PostgresDatabase) -> None:
    config = load_config()

    user_email = config.email.user_email
    user_name = config.email.user_name or user_email.split("@")[0]
    vip_senders = list(config.preferences.vip_senders) if config.preferences.vip_senders else []

    imap_jobs_q.append_event(db, job_id, "Loading unread emails from cache")

    emails = email_queries.search_emails(db, folder="INBOX", is_unread=True, limit=500)
    total = len(emails)
    imap_jobs_q.update_progress(db, job_id, total_estimate=total, processed=0)
    imap_jobs_q.append_event(db, job_id, f"Found {total} unread emails to triage")

    if total == 0:
        imap_jobs_q.append_event(db, job_id, "No unread emails, nothing to triage")
        return

    llm_client = None
    try:
        from workspace_secretary.assistant.llm import get_llm_client
        llm_client = get_llm_client(config)
    except Exception as e:
        logger.warning(f"LLM client unavailable, using fast classification only: {e}")

    imap_jobs_q.append_event(db, job_id, "Running classifier pipeline")
    triage_result = await triage_emails(
        emails, llm_client, user_email, user_name, vip_senders
    )

    imap_jobs_q.append_event(
        db,
        job_id,
        f"Classified {triage_result.total_processed} emails: "
        f"{len(triage_result.high_confidence)} high confidence, "
        f"{len(triage_result.needs_review)} needs review",
    )

    processed = 0
    for cat, classifications in triage_result.by_category.items():
        for c in classifications:
            email = next((e for e in emails if e.get("uid") == c.uid), None)
            if email is None:
                continue

            imap_jobs_q.insert_candidate(
                db,
                job_id,
                uid=c.uid,
                folder=email.get("folder", "INBOX"),
                message_id=email.get("message_id"),
                from_addr=email.get("from_addr"),
                to_addr=email.get("to_addr"),
                cc_addr=email.get("cc_addr"),
                subject=email.get("subject"),
                date=email.get("date"),
                body_preview=(email.get("body_text") or "")[:300],
                category=c.category.value,
                confidence=c.confidence,
                signals={"reasoning": c.reasoning},
                proposed_actions=c.actions,
            )
            processed += 1

            if processed % 50 == 0:
                imap_jobs_q.update_progress(db, job_id, processed=processed)

    imap_jobs_q.update_progress(db, job_id, processed=processed)
    imap_jobs_q.append_event(db, job_id, f"Stored {processed} candidates for review")


def _claim_next_sync_job(db: PostgresDatabase) -> str | None:
    job = imap_jobs_q.claim_next_job(db, job_type="sync")
    if not job:
        return None
    return str(job["job_id"])


def _claim_next_triage_preview_job(db: PostgresDatabase) -> str | None:
    job = imap_jobs_q.claim_next_job(db, job_type="triage_preview")
    if not job:
        return None
    return str(job["job_id"])


def _claim_next_approved_triage_job(db: PostgresDatabase) -> dict | None:
    return imap_jobs_q.claim_next_approved_job(db, job_type="triage_preview")


def _claim_next_bulk_cleanup_job(db: PostgresDatabase) -> str | None:
    job = imap_jobs_q.claim_next_job(db, job_type="bulk_cleanup")
    if not job:
        return None
    return str(job["job_id"])


def _claim_next_triage_apply_job(db: PostgresDatabase) -> str | None:
    job = imap_jobs_q.claim_next_job(db, job_type="triage_apply")
    if not job:
        return None
    return str(job["job_id"])


def _run_bulk_cleanup_job_sync(job_id: str, db: PostgresDatabase) -> None:
    job = imap_jobs_q.get_job(db, job_id)
    if not job:
        raise RuntimeError(f"Job {job_id} not found")

    payload = job.get("payload", {})
    uids_data = payload.get("uids", [])
    destination = payload.get("destination", "Secretary/Auto-Cleaned")
    mark_read = payload.get("mark_read", True)

    if not uids_data:
        imap_jobs_q.append_event(db, job_id, "No UIDs in payload")
        return

    total = len(uids_data)
    imap_jobs_q.append_event(db, job_id, f"Processing {total} emails for cleanup")
    imap_jobs_q.update_progress(db, job_id, total_estimate=total, processed=0)

    batch_size = 10
    processed = 0
    failed = 0

    with get_imap_from_pool() as imap_client:
        for i in range(0, total, batch_size):
            if imap_jobs_q.is_cancel_requested(db, job_id):
                imap_jobs_q.append_event(db, job_id, "Cleanup cancelled by user")
                break

            batch = uids_data[i : i + batch_size]
            for item in batch:
                uid = item["uid"]
                folder = item.get("folder", "INBOX")

                try:
                    if mark_read:
                        imap_client.mark_email(uid, folder, "read")
                        email_queries.mark_email_read(db, uid, folder, is_read=True)

                    imap_client.move_email(uid, folder, destination)
                    email_queries.delete_email(db, uid, folder)

                    processed += 1

                except Exception as e:
                    logger.warning(f"Failed to cleanup UID {uid} in {folder}: {e}")
                    failed += 1

            imap_jobs_q.update_progress(db, job_id, processed=processed)
            if (i // batch_size + 1) % 5 == 0:
                imap_jobs_q.append_event(
                    db, job_id, f"Progress: {processed}/{total} processed, {failed} failed"
                )

    imap_jobs_q.append_event(
        db, job_id, f"Cleanup complete: {processed} moved, {failed} failed"
    )


def _run_triage_apply_job_sync(job_id: str, db: PostgresDatabase) -> None:
    """Apply labels and actions from triage classifications (sync, runs in thread).
    
    Job payload format:
    {
        "items": [
            {
                "uid": 12345,
                "folder": "INBOX",
                "label": "Secretary/Newsletter",
                "actions": ["mark_read", "archive"],
                "confidence": 0.95
            },
            ...
        ],
        "auto_apply_high_confidence": true
    }
    """
    job = imap_jobs_q.get_job(db, job_id)
    if not job:
        raise RuntimeError(f"Job {job_id} not found")

    payload = job.get("payload", {})
    items = payload.get("items", [])
    auto_apply_high_confidence = payload.get("auto_apply_high_confidence", True)

    if not items:
        imap_jobs_q.append_event(db, job_id, "No items in payload")
        return

    total = len(items)
    imap_jobs_q.append_event(db, job_id, f"Applying labels to {total} emails")
    imap_jobs_q.update_progress(db, job_id, total_estimate=total, processed=0)

    batch_size = 10
    processed = 0
    labels_applied = 0
    labels_removed = 0
    marked_read = 0
    archived = 0
    failed = 0

    with get_imap_from_pool() as imap_client:
        for i in range(0, total, batch_size):
            if imap_jobs_q.is_cancel_requested(db, job_id):
                imap_jobs_q.append_event(db, job_id, "Triage apply cancelled by user")
                break

            batch = items[i : i + batch_size]
            for item in batch:
                uid = item.get("uid")
                folder = item.get("folder", "INBOX")
                label = item.get("label")
                remove_label = item.get("remove_label")
                actions = item.get("actions", [])
                confidence = item.get("confidence", 0)

                if not uid:
                    continue

                try:
                    if remove_label:
                        try:
                            imap_client.remove_gmail_labels(uid, folder, [remove_label])
                            email_queries.remove_email_label(db, uid, folder, remove_label)
                            labels_removed += 1
                        except Exception as e:
                            logger.warning(f"Failed to remove label {remove_label} from {uid}: {e}")

                    if label:
                        try:
                            imap_client.add_gmail_labels(uid, folder, [label])
                            email_queries.add_email_label(db, uid, folder, label)
                            labels_applied += 1
                        except Exception as e:
                            logger.warning(f"Failed to apply label {label} to {uid}: {e}")

                    if confidence >= 0.90 and auto_apply_high_confidence:
                        if "mark_read" in actions:
                            try:
                                imap_client.mark_email(uid, folder, "read")
                                email_queries.mark_email_read(db, uid, folder, is_read=True)
                                marked_read += 1
                            except Exception as e:
                                logger.warning(f"Failed to mark {uid} as read: {e}")

                        if "archive" in actions:
                            try:
                                imap_client.move_email(uid, folder, "[Gmail]/All Mail")
                                email_queries.delete_email(db, uid, folder)
                                archived += 1
                            except Exception as e:
                                logger.warning(f"Failed to archive {uid}: {e}")

                    processed += 1

                except Exception as e:
                    logger.warning(f"Failed to process UID {uid}: {e}")
                    failed += 1

            imap_jobs_q.update_progress(db, job_id, processed=processed)
            if (i // batch_size + 1) % 5 == 0:
                imap_jobs_q.append_event(
                    db, job_id, 
                    f"Progress: {processed}/{total} - +{labels_applied}/-{labels_removed} labels, {marked_read} read, {archived} archive"
                )

    imap_jobs_q.append_event(
        db, job_id, 
        f"Triage apply complete: +{labels_applied}/-{labels_removed} labels, {marked_read} read, {archived} archived, {failed} failed"
    )


def _run_triage_execute_job_sync(job_id: str, db: PostgresDatabase) -> None:
    approval = imap_jobs_q.get_approval(db, job_id)
    if approval is None:
        raise RuntimeError("Cannot execute triage job without approval")

    payload = approval.get("approval_payload", {})
    candidate_ids = payload.get("candidate_ids", [])
    actions = set(payload.get("actions", []))

    if not candidate_ids:
        imap_jobs_q.append_event(db, job_id, "No candidates in approval payload")
        return

    imap_jobs_q.append_event(db, job_id, f"Executing approved actions for {len(candidate_ids)} candidates")

    candidates = imap_jobs_q.list_candidates(db, job_id, limit=10000)
    selected = [c for c in candidates if c["id"] in candidate_ids]

    if not selected:
        imap_jobs_q.append_event(db, job_id, "No matching candidates found in DB")
        return

    total = len(selected)
    batch_size = 10
    processed = 0
    failed = 0

    imap_jobs_q.update_progress(db, job_id, total_estimate=total, processed=0)

    with get_imap_from_pool() as imap_client:
        for i in range(0, total, batch_size):
            if imap_jobs_q.is_cancel_requested(db, job_id):
                imap_jobs_q.append_event(db, job_id, "Execution cancelled by user")
                break

            batch = selected[i : i + batch_size]
            for cand in batch:
                uid = cand["uid"]
                folder = cand["folder"]
                category = cand["category"]

                try:
                    if "mark_read" in actions:
                        imap_client.mark_email(uid, folder, "read")
                        email_queries.mark_email_read(db, uid, folder, is_read=True)

                    if "archive" in actions:
                        imap_client.move_email(uid, folder, "[Gmail]/All Mail")
                        email_queries.delete_email(db, uid, folder)

                    label = f"Secretary/{category.replace('_', '-').title()}"
                    if "add_label" in actions:
                        imap_client.add_gmail_labels(uid, folder, [label])

                    imap_jobs_q.set_candidate_decision(db, cand["id"], "executed")
                    processed += 1

                except Exception as e:
                    logger.exception(f"Failed to process candidate {cand['id']}")
                    imap_jobs_q.set_candidate_decision(db, cand["id"], f"error: {e}")
                    failed += 1

            imap_jobs_q.update_progress(db, job_id, processed=processed)
            imap_jobs_q.append_event(
                db, job_id, f"Processed batch {i // batch_size + 1}: {processed} done, {failed} failed"
            )

    imap_jobs_q.append_event(
        db, job_id, f"Execution complete: {processed} successful, {failed} failed"
    )


async def run_forever(cfg: ExecutorConfig = ExecutorConfig()) -> None:
    config = load_config()
    if config.database.backend.value != "postgres":
        raise RuntimeError("imap-executor requires postgres database backend")

    db_cfg = config.database.postgres
    db = PostgresDatabase(
        host=db_cfg.host,
        port=db_cfg.port,
        database=db_cfg.database,
        user=db_cfg.user,
        password=db_cfg.password,
        ssl_mode=db_cfg.ssl_mode,
        embedding_dimensions=config.database.embeddings.dimensions,
    )
    db.initialize()

    with db.connection() as conn:
        with conn.cursor() as cur:
            from workspace_secretary.db import schema

            schema.initialize_all_schemas(
                cur, vector_type=db._vector_type, embedding_dimensions=db.embedding_dimensions
            )
            conn.commit()

    sem = asyncio.Semaphore(cfg.max_concurrent_jobs)

    async def _sync_worker(job_id: str) -> None:
        async with sem:
            try:
                imap_jobs_q.append_event(db, job_id, "Job claimed")
                await _run_sync_job(job_id)
                imap_jobs_q.mark_finished(db, job_id, status="completed")
            except Exception as e:
                logger.exception("Sync job failed")
                imap_jobs_q.append_event(db, job_id, f"Job failed: {e}", level="error")
                imap_jobs_q.mark_finished(db, job_id, status="failed", error=str(e))

    async def _triage_preview_worker(job_id: str) -> None:
        async with sem:
            try:
                imap_jobs_q.append_event(db, job_id, "Triage preview job claimed")
                await _run_triage_preview_job(job_id, db)
                imap_jobs_q.mark_finished(db, job_id, status="completed")
            except Exception as e:
                logger.exception("Triage preview job failed")
                imap_jobs_q.append_event(db, job_id, f"Job failed: {e}", level="error")
                imap_jobs_q.mark_finished(db, job_id, status="failed", error=str(e))

    async def _triage_execute_worker(job_id: str) -> None:
        async with sem:
            try:
                imap_jobs_q.append_event(db, job_id, "Executing approved triage actions")
                await asyncio.to_thread(_run_triage_execute_job_sync, job_id, db)
                imap_jobs_q.mark_finished(db, job_id, status="completed")
            except Exception as e:
                logger.exception("Triage execute job failed")
                imap_jobs_q.append_event(db, job_id, f"Job failed: {e}", level="error")
                imap_jobs_q.mark_finished(db, job_id, status="failed", error=str(e))

    async def _bulk_cleanup_worker(job_id: str) -> None:
        async with sem:
            try:
                imap_jobs_q.append_event(db, job_id, "Bulk cleanup job started")
                await asyncio.to_thread(_run_bulk_cleanup_job_sync, job_id, db)
                imap_jobs_q.mark_finished(db, job_id, status="completed")
            except Exception as e:
                logger.exception("Bulk cleanup job failed")
                imap_jobs_q.append_event(db, job_id, f"Job failed: {e}", level="error")
                imap_jobs_q.mark_finished(db, job_id, status="failed", error=str(e))

    async def _triage_apply_worker(job_id: str) -> None:
        async with sem:
            try:
                imap_jobs_q.append_event(db, job_id, "Triage apply job started")
                await asyncio.to_thread(_run_triage_apply_job_sync, job_id, db)
                imap_jobs_q.mark_finished(db, job_id, status="completed")
            except Exception as e:
                logger.exception("Triage apply job failed")
                imap_jobs_q.append_event(db, job_id, f"Job failed: {e}", level="error")
                imap_jobs_q.mark_finished(db, job_id, status="failed", error=str(e))

    running: set[asyncio.Task[None]] = set()

    while True:
        done = {t for t in running if t.done()}
        running -= done

        while sem.locked() is False and len(running) < cfg.max_concurrent_jobs:
            job_id = await asyncio.to_thread(_claim_next_sync_job, db)
            if job_id:
                running.add(asyncio.create_task(_sync_worker(job_id)))
                continue

            job_id = await asyncio.to_thread(_claim_next_triage_preview_job, db)
            if job_id:
                running.add(asyncio.create_task(_triage_preview_worker(job_id)))
                continue

            approved_job = await asyncio.to_thread(_claim_next_approved_triage_job, db)
            if approved_job:
                running.add(asyncio.create_task(_triage_execute_worker(str(approved_job["job_id"]))))
                continue

            job_id = await asyncio.to_thread(_claim_next_bulk_cleanup_job, db)
            if job_id:
                running.add(asyncio.create_task(_bulk_cleanup_worker(job_id)))
                continue

            job_id = await asyncio.to_thread(_claim_next_triage_apply_job, db)
            if job_id:
                running.add(asyncio.create_task(_triage_apply_worker(job_id)))
                continue

            break

        await asyncio.sleep(cfg.poll_interval_s)
