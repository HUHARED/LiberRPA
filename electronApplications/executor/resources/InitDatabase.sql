-- FileName: InitDatabase.sql
PRAGMA foreign_keys = ON;

CREATE TABLE
    project (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL CHECK (LENGTH(TRIM(name)) > 0),
        version TEXT NOT NULL CHECK (LENGTH(TRIM(version)) > 0),
        description TEXT NOT NULL DEFAULT '',
        version_summary TEXT NOT NULL DEFAULT '',
        python_environment_name TEXT NOT NULL DEFAULT 'default' CHECK (LENGTH(TRIM(python_environment_name)) > 0),
        retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count BETWEEN 0 AND 3),
        timeout_min INTEGER NOT NULL DEFAULT 0 CHECK (timeout_min >= 0),
        builtin_log_level TEXT NOT NULL DEFAULT 'DEBUG' CHECK (
            builtin_log_level IN (
                'VERBOSE',
                'DEBUG',
                'INFO',
                'WARNING',
                'ERROR',
                'CRITICAL'
            )
        ),
        -- SQLite STRICT tables store Boolean values as INTEGER 0 or 1.
        builtin_record_video INTEGER NOT NULL DEFAULT 0 CHECK (builtin_record_video IN (0, 1)),
        builtin_stop_shortcut INTEGER NOT NULL DEFAULT 1 CHECK (builtin_stop_shortcut IN (0, 1)),
        builtin_highlight_ui INTEGER NOT NULL DEFAULT 0 CHECK (builtin_highlight_ui IN (0, 1)),
        custom_prj_args TEXT NOT NULL DEFAULT '[]',
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= 0),
        UNIQUE (name, version)
    ) STRICT;

CREATE TABLE
    schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE CHECK (LENGTH(TRIM(name)) > 0),
        project_id INTEGER NOT NULL CHECK (project_id > 0),
        cron TEXT NOT NULL CHECK (LENGTH(TRIM(cron)) > 0),
        run_conflict_policy TEXT NOT NULL DEFAULT 'skip' CHECK (
            run_conflict_policy IN ('skip', 'wait', 'concurrent')
        ),
        period_start_ms INTEGER NOT NULL CHECK (period_start_ms >= 0),
        period_end_ms INTEGER NOT NULL CHECK (period_end_ms > period_start_ms),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count BETWEEN 0 AND 3),
        timeout_min INTEGER NOT NULL DEFAULT 0 CHECK (timeout_min >= 0),
        builtin_log_level TEXT NOT NULL DEFAULT 'DEBUG' CHECK (
            builtin_log_level IN (
                'VERBOSE',
                'DEBUG',
                'INFO',
                'WARNING',
                'ERROR',
                'CRITICAL'
            )
        ),
        builtin_record_video INTEGER NOT NULL DEFAULT 0 CHECK (builtin_record_video IN (0, 1)),
        builtin_stop_shortcut INTEGER NOT NULL DEFAULT 1 CHECK (builtin_stop_shortcut IN (0, 1)),
        builtin_highlight_ui INTEGER NOT NULL DEFAULT 0 CHECK (builtin_highlight_ui IN (0, 1)),
        custom_prj_args TEXT NOT NULL DEFAULT '[]',
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= 0),
        FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE RESTRICT
    ) STRICT;

CREATE TABLE
    run_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL CHECK (source IN ('local', 'console')),
        run_id TEXT NOT NULL UNIQUE,
        job_id TEXT NOT NULL,
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 4),
        inputs TEXT NOT NULL,
        -- NOTE: Keep this envelope aligned with RunOutputs in shared/run.ts; item validation stays in runState.ts.
        outputs TEXT NOT NULL CHECK (
            CASE
                WHEN JSON_VALID(outputs) THEN (
                    JSON_TYPE(outputs) IS 'object'
                    AND JSON_TYPE(outputs, '$.status') IS 'text'
                    AND JSON_TYPE(outputs, '$.unavailableKeys') IS 'array'
                    AND JSON_TYPE(outputs, '$.reason') IS 'text'
                    AND CASE JSON_EXTRACT(outputs, '$.status')
                        WHEN 'complete' THEN JSON_TYPE(outputs, '$.values') IS 'array'
                        AND JSON_ARRAY_LENGTH(outputs, '$.unavailableKeys') = 0
                        WHEN 'partial' THEN JSON_TYPE(outputs, '$.values') IS 'array'
                        AND JSON_ARRAY_LENGTH(outputs, '$.unavailableKeys') > 0
                        WHEN 'unavailable' THEN JSON_TYPE(outputs, '$.values') IS 'null'
                        AND JSON_ARRAY_LENGTH(outputs, '$.unavailableKeys') = 0
                        ELSE 0
                    END
                ) IS TRUE
                ELSE 0
            END
        ),
        error_summary TEXT NULL,
        schedule_name TEXT NULL DEFAULT NULL,
        project_id INTEGER NULL CHECK (
            project_id IS NULL
            OR project_id > 0
        ),
        project_name TEXT NOT NULL CHECK (LENGTH(TRIM(project_name)) > 0),
        project_version TEXT NOT NULL CHECK (LENGTH(TRIM(project_version)) > 0),
        python_environment_name TEXT NOT NULL CHECK (LENGTH(TRIM(python_environment_name)) > 0),
        run_started_at_ms INTEGER NOT NULL CHECK (run_started_at_ms >= 0),
        run_ended_at_ms INTEGER NULL DEFAULT NULL CHECK (
            run_ended_at_ms IS NULL
            OR run_ended_at_ms >= run_started_at_ms
        ),
        status TEXT NOT NULL DEFAULT 'running' CHECK (
            status IN (
                'running',
                'completed',
                'error',
                'canceled',
                'timed_out',
                'interrupted',
                'unknown'
            )
        ),
        log_path TEXT NOT NULL CHECK (LENGTH(TRIM(log_path)) > 0),
        no_log_folder INTEGER NOT NULL DEFAULT 0 CHECK (no_log_folder IN (0, 1)),
        no_log_video INTEGER NOT NULL DEFAULT 0 CHECK (no_log_video IN (0, 1)),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= 0),
        CHECK (
            (
                status IN ('running', 'unknown')
                AND run_ended_at_ms IS NULL
            )
            OR (
                status IN (
                    'completed',
                    'error',
                    'canceled',
                    'timed_out',
                    'interrupted'
                )
                AND (
                    run_ended_at_ms IS NOT NULL
                    OR status = 'interrupted'
                )
            )
        )
    ) STRICT;

CREATE INDEX idx_schedule_project_id ON schedule (project_id);

CREATE INDEX idx_run_history_run_started_at_ms ON run_history (run_started_at_ms DESC);

CREATE TABLE
    console_work (
        id TEXT PRIMARY KEY,
        session_key TEXT NOT NULL,
        state TEXT NOT NULL CHECK (
            state IN (
                'preparing',
                'permitted',
                'launching',
                'running',
                'finished',
                'unknown'
            )
        ),
        content TEXT NOT NULL,
        updated_at_ms INTEGER NOT NULL
    ) STRICT;

CREATE TABLE
    console_event (
        id TEXT PRIMARY KEY,
        session_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        rejected INTEGER NOT NULL DEFAULT 0 CHECK (rejected IN (0, 1)),
        rejection_code TEXT NULL CHECK (
            rejection_code IS NULL
            OR LENGTH(TRIM(rejection_code)) > 0
        ),
        rejection_message TEXT NULL,
        rejected_at_ms INTEGER NULL CHECK (
            rejected_at_ms IS NULL
            OR rejected_at_ms >= 0
        ),
        CHECK (
            (
                rejection_code IS NULL
                AND rejection_message IS NULL
                AND rejected_at_ms IS NULL
            )
            OR (
                rejected = 1
                AND rejection_code IS NOT NULL
                AND rejection_message IS NOT NULL
                AND rejected_at_ms IS NOT NULL
            )
        )
    ) STRICT;

CREATE INDEX idx_console_work_run_session ON console_work (
    JSON_EXTRACT(content, '$.assignment.run_id'),
    session_key
);

CREATE INDEX idx_console_work_pending_logs ON console_work (session_key)
WHERE
    (
        (
            JSON_TYPE(content, '$.started') = 'object'
            AND JSON_EXTRACT(content, '$.logsComplete') = 0
        )
        OR (
            JSON_TYPE(content, '$.ended') = 'object'
            AND JSON_EXTRACT(
                content,
                '$.assignment.snapshot.builtin_record_video'
            ) = 1
            AND COALESCE(JSON_EXTRACT(content, '$.recording.status'), '') NOT IN ('ready', 'unavailable')
        )
    );

CREATE INDEX idx_console_event_pending_session_key ON console_event (session_key)
WHERE
    rejected = 0;

PRAGMA user_version = 2;