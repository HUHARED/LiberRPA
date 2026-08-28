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
        enable INTEGER NOT NULL DEFAULT 1 CHECK (enable IN (0, 1)),
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
        schedule_name TEXT NULL DEFAULT NULL,
        project_id INTEGER NOT NULL CHECK (project_id > 0),
        project_name TEXT NOT NULL CHECK (LENGTH(TRIM(project_name)) > 0),
        project_version TEXT NOT NULL CHECK (LENGTH(TRIM(project_version)) > 0),
        python_environment_name TEXT NOT NULL CHECK (LENGTH(TRIM(python_environment_name)) > 0),
        run_started_at_ms INTEGER NOT NULL CHECK (run_started_at_ms >= 0),
        run_ended_at_ms INTEGER NULL DEFAULT NULL CHECK (
            run_ended_at_ms IS NULL
            OR run_ended_at_ms >= 0
        ),
        status TEXT NOT NULL DEFAULT 'running' CHECK (
            status IN (
                'running',
                'completed',
                'error',
                'cancel',
                'timeout',
                'interrupted'
            )
        ),
        log_path TEXT NOT NULL CHECK (LENGTH(TRIM(log_path)) > 0),
        log_root_path TEXT NOT NULL CHECK (LENGTH(TRIM(log_root_path)) > 0),
        no_log_folder INTEGER NOT NULL DEFAULT 0 CHECK (no_log_folder IN (0, 1)),
        no_log_video INTEGER NOT NULL DEFAULT 0 CHECK (no_log_video IN (0, 1)),
        created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
        updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= 0),
        CHECK (
            (
                status IN ('running', 'interrupted')
                AND run_ended_at_ms IS NULL
            )
            OR (
                status IN ('completed', 'error', 'cancel', 'timeout')
                AND run_ended_at_ms IS NOT NULL
            )
        )
    ) STRICT;

CREATE INDEX idx_schedule_project_id ON schedule (project_id);

CREATE INDEX idx_run_history_run_started_at_ms ON run_history (run_started_at_ms DESC);

PRAGMA user_version = 1;