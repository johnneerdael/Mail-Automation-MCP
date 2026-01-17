"""
Idempotent schema initialization for PostgreSQL.

Both engine and web can call these functions safely.
Self-healing logic (type migrations, index repairs) lives in engine only.
"""

from typing import Any


def initialize_core_schema(
    cur: Any, vector_type: str, embedding_dimensions: int
) -> None:
    """
    Initialize core tables: emails, folder_state, user_preferences, sync_errors, system_health.

    Args:
        cur: psycopg cursor
        vector_type: "vector" or "halfvec"
        embedding_dimensions: embedding vector size
    """
    # Enable pgvector extension
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Emails table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS emails (
            uid INTEGER NOT NULL,
            folder TEXT NOT NULL,
            message_id TEXT,
            subject TEXT,
            from_addr TEXT,
            to_addr TEXT,
            cc_addr TEXT,
            bcc_addr TEXT,
            date TIMESTAMPTZ,
            internal_date TIMESTAMPTZ,
            body_text TEXT,
            body_html TEXT,
            flags TEXT,
            is_unread BOOLEAN,
            is_important BOOLEAN,
            size INTEGER,
            modseq BIGINT,
            synced_at TIMESTAMPTZ DEFAULT NOW(),
            in_reply_to TEXT,
            references_header TEXT,
            content_hash TEXT,
            gmail_thread_id BIGINT,
            gmail_msgid BIGINT,
            gmail_labels JSONB,
            has_attachments BOOLEAN DEFAULT FALSE,
            attachment_filenames JSONB,
            auth_results_raw TEXT,
            spf TEXT,
            dkim TEXT,
            dmarc TEXT,
            is_suspicious_sender BOOLEAN DEFAULT FALSE,
            suspicious_sender_signals JSONB,
            security_score INTEGER DEFAULT 100,
            warning_type TEXT,
            PRIMARY KEY (uid, folder)
        )
        """
    )

    # Add columns if missing (idempotent migrations)
    cur.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS auth_results_raw TEXT")
    cur.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS spf TEXT")
    cur.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS dkim TEXT")
    cur.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS dmarc TEXT")
    cur.execute(
        "ALTER TABLE emails ADD COLUMN IF NOT EXISTS is_suspicious_sender BOOLEAN DEFAULT FALSE"
    )
    cur.execute(
        "ALTER TABLE emails ADD COLUMN IF NOT EXISTS suspicious_sender_signals JSONB"
    )
    cur.execute(
        "ALTER TABLE emails ADD COLUMN IF NOT EXISTS security_score INTEGER DEFAULT 100"
    )
    cur.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS warning_type TEXT")

    # Folder state
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS folder_state (
            folder TEXT PRIMARY KEY,
            uidvalidity INTEGER,
            uidnext INTEGER,
            highestmodseq BIGINT,
            last_sync TIMESTAMPTZ
        )
        """
    )

    # User preferences
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            prefs_json TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    # Sync errors
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_errors (
            id SERIAL PRIMARY KEY,
            folder TEXT,
            email_uid INTEGER,
            error_type TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolution TEXT
        )
        """
    )

    # System health
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_health (
            id SERIAL PRIMARY KEY,
            component TEXT NOT NULL,
            metric TEXT NOT NULL,
            value TEXT,
            recorded_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def initialize_embeddings_schema(
    cur: Any, vector_type: str, embedding_dimensions: int
) -> None:
    """
    Initialize email_embeddings table (idempotent).

    Self-healing type/index corrections are NOT done here (engine-only).
    """
    expected_type = f"{vector_type}({embedding_dimensions})"

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS email_embeddings (
            email_uid INTEGER NOT NULL,
            email_folder TEXT NOT NULL,
            embedding {expected_type},
            model TEXT,
            content_hash TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (email_uid, email_folder),
            FOREIGN KEY (email_uid, email_folder) REFERENCES emails(uid, folder) ON DELETE CASCADE
        )
        """
    )


def initialize_contacts_schema(cur: Any) -> None:
    """Initialize contacts tables."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            display_name VARCHAR(255),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email_count INT DEFAULT 0,
            last_email_date TIMESTAMPTZ,
            first_email_date TIMESTAMPTZ,
            is_vip BOOLEAN DEFAULT FALSE,
            is_internal BOOLEAN DEFAULT FALSE,
            organization VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('english', 
                    coalesce(display_name, '') || ' ' || 
                    coalesce(email, '') || ' ' ||
                    coalesce(organization, '')
                )
            ) STORED
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_interactions (
            id SERIAL PRIMARY KEY,
            contact_id INT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            email_uid INT NOT NULL,
            email_folder VARCHAR(100) NOT NULL,
            direction VARCHAR(10) NOT NULL,
            subject TEXT,
            email_date TIMESTAMPTZ NOT NULL,
            message_id VARCHAR(500),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_interaction UNIQUE (contact_id, email_uid, email_folder, direction)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_notes (
            id SERIAL PRIMARY KEY,
            contact_id INT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            note TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_tags (
            id SERIAL PRIMARY KEY,
            contact_id INT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            tag VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_contact_tag UNIQUE (contact_id, tag)
        )
        """
    )


def initialize_calendar_schema(cur: Any) -> None:
    """Initialize calendar sync and cache tables."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_sync_state (
            calendar_id TEXT PRIMARY KEY,
            sync_token TEXT,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            last_full_sync_at TIMESTAMPTZ,
            last_incremental_sync_at TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'ok',
            last_error TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_events_cache (
            calendar_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            etag TEXT,
            updated TIMESTAMPTZ,
            status TEXT,
            start_ts_utc TIMESTAMPTZ,
            end_ts_utc TIMESTAMPTZ,
            start_date DATE,
            end_date DATE,
            is_all_day BOOLEAN DEFAULT FALSE,
            summary TEXT,
            location TEXT,
            local_status TEXT NOT NULL DEFAULT 'synced',
            raw_json JSONB NOT NULL,
            PRIMARY KEY (calendar_id, event_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_outbox (
            id UUID PRIMARY KEY,
            op_type TEXT NOT NULL,
            calendar_id TEXT NOT NULL,
            event_id TEXT,
            local_temp_id TEXT,
            payload_json JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TIMESTAMPTZ,
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS booking_links (
            link_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            calendar_id TEXT NOT NULL,
            host_name TEXT,
            meeting_title TEXT,
            meeting_description TEXT,
            timezone TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 30,
            availability_days INTEGER NOT NULL DEFAULT 14,
            availability_start_hour INTEGER NOT NULL DEFAULT 11,
            availability_end_hour INTEGER NOT NULL DEFAULT 22,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def initialize_mutation_journal(cur: Any) -> None:
    """Initialize mutation journal (engine-only table, but idempotent)."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mutation_journal (
            id SERIAL PRIMARY KEY,
            email_uid INTEGER NOT NULL,
            email_folder TEXT NOT NULL,
            action TEXT NOT NULL,
            params JSONB,
            status TEXT DEFAULT 'PENDING',
            pre_state JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            error TEXT,
            FOREIGN KEY (email_uid, email_folder) REFERENCES emails(uid, folder) ON DELETE CASCADE
        )
        """
    )


def initialize_imap_jobs_schema(cur: Any) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS imap_jobs (
            job_id UUID PRIMARY KEY,
            job_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP NULL,
            finished_at TIMESTAMP NULL,
            total_estimate INT DEFAULT 0,
            processed INT DEFAULT 0,
            cancel_requested BOOLEAN DEFAULT FALSE,
            error TEXT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_imap_jobs_status_created_at
            ON imap_jobs(status, created_at)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS imap_job_events (
            id BIGSERIAL PRIMARY KEY,
            job_id UUID NOT NULL REFERENCES imap_jobs(job_id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10) NOT NULL DEFAULT 'info',
            message TEXT NOT NULL,
            data JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_imap_job_events_job_id_id
            ON imap_job_events(job_id, id)
        """
    )

    # Approval columns on imap_jobs (idempotent ADD COLUMN IF NOT EXISTS)
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'imap_jobs' AND column_name = 'approved_at'
            ) THEN
                ALTER TABLE imap_jobs ADD COLUMN approved_at TIMESTAMP NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'imap_jobs' AND column_name = 'approved_by'
            ) THEN
                ALTER TABLE imap_jobs ADD COLUMN approved_by VARCHAR(255) NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'imap_jobs' AND column_name = 'approval_payload'
            ) THEN
                ALTER TABLE imap_jobs ADD COLUMN approval_payload JSONB NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'imap_jobs' AND column_name = 'payload'
            ) THEN
                ALTER TABLE imap_jobs ADD COLUMN payload JSONB NULL;
            END IF;
        END
        $$;
        """
    )

    # Candidates table for triage/cleanup preview results
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS imap_job_candidates (
            id BIGSERIAL PRIMARY KEY,
            job_id UUID NOT NULL REFERENCES imap_jobs(job_id) ON DELETE CASCADE,
            uid INT NOT NULL,
            folder VARCHAR(255) NOT NULL,
            message_id VARCHAR(512) NULL,
            from_addr VARCHAR(512) NULL,
            to_addr TEXT NULL,
            cc_addr TEXT NULL,
            subject TEXT NULL,
            date TIMESTAMP NULL,
            body_preview TEXT NULL,
            category VARCHAR(50) NOT NULL,
            confidence REAL NOT NULL,
            signals JSONB NOT NULL DEFAULT '{}'::jsonb,
            proposed_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
            user_decision VARCHAR(20) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_imap_job_candidates_job_id
            ON imap_job_candidates(job_id)
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_imap_job_candidates_confidence
            ON imap_job_candidates(job_id, confidence DESC)
        """
    )


def create_indexes(cur: Any, vector_type: str) -> None:
    """
    Create all indexes (idempotent).

    NOTE: Embeddings index is created WITHOUT self-heal check.
    Engine will run self-heal separately if needed.
    """
    # Email indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(folder)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emails_unread ON emails(is_unread)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_addr)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_content_hash ON emails(content_hash)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_gmail_thread_id ON emails(gmail_thread_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_gmail_labels ON emails USING gin(gmail_labels)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_has_attachments ON emails(has_attachments) WHERE has_attachments = true"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_internal_date ON emails(internal_date)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_emails_is_suspicious_sender ON emails(is_suspicious_sender)"
    )

    # FTS index
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emails_fts
        ON emails USING gin(to_tsvector('english', COALESCE(subject, '') || ' ' || COALESCE(body_text, '')))
        """
    )

    # Embeddings index (basic creation, no self-heal)
    ops = "halfvec_ip_ops" if vector_type == "halfvec" else "vector_ip_ops"
    cur.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_embeddings_vector
        ON email_embeddings USING hnsw (embedding {ops})
        """
    )

    # Contact indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_last_email_date ON contacts(last_email_date DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_email_count ON contacts(email_count DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_search_vector ON contacts USING GIN(search_vector)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_is_vip ON contacts(is_vip) WHERE is_vip = TRUE"
    )

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_interactions_contact_id ON contact_interactions(contact_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_interactions_email_date ON contact_interactions(email_date DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_interactions_email_uid ON contact_interactions(email_uid, email_folder)"
    )

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_notes_contact_id ON contact_notes(contact_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_tags_contact_id ON contact_tags(contact_id)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contact_tags_tag ON contact_tags(tag)")

    # Calendar indexes
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cal_events_start_ts ON calendar_events_cache(calendar_id, start_ts_utc)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cal_events_start_date ON calendar_events_cache(calendar_id, start_date)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cal_outbox_status ON calendar_outbox(status, created_at)"
    )


def initialize_all_schemas(
    cur: Any, vector_type: str, embedding_dimensions: int
) -> None:
    initialize_core_schema(cur, vector_type, embedding_dimensions)
    initialize_embeddings_schema(cur, vector_type, embedding_dimensions)
    initialize_contacts_schema(cur)
    initialize_calendar_schema(cur)
    initialize_mutation_journal(cur)
    initialize_imap_jobs_schema(cur)
    create_indexes(cur, vector_type)
