CREATE TABLE
    project_local (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        timeout_min INTEGER NOT NULL DEFAULT 0,
        buildin_log_level TEXT NOT NULL DEFAULT 'DEBUG' CHECK (
            buildin_log_level IN (
                'VERBOSE',
                'DEBUG',
                'INFO',
                'WARNING',
                'ERROR',
                'CRITICAL'
            )
        ),
        buildin_record_video BOOLEAN NOT NULL DEFAULT FALSE,
        buildin_stop_shortcut BOOLEAN NOT NULL DEFAULT TRUE,
        buildin_highlight_ui BOOLEAN NOT NULL DEFAULT FALSE,
        custom_prj_args TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime')),
        updated_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime')),
        UNIQUE (name, version)
    );

CREATE TABLE
    task_scheduler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        project_source TEXT NOT NULL DEFAULT 'local' CHECK (project_source IN ('local', 'console')),
        project_id INTEGER NOT NULL,
        cron TEXT NOT NULL,
        when_others_running TEXT NOT NULL DEFAULT 'cancel' CHECK (when_others_running IN ('cancel', 'wait', 'run')),
        period_start DATETIME NOT NULL,
        period_end DATETIME NOT NULL,
        enable BOOLEAN NOT NULL DEFAULT TRUE,
        timeout_min INTEGER NOT NULL DEFAULT 0,
        buildin_log_level TEXT NOT NULL DEFAULT 'DEBUG' CHECK (
            buildin_log_level IN (
                'VERBOSE',
                'DEBUG',
                'INFO',
                'WARNING',
                'ERROR',
                'CRITICAL'
            )
        ),
        buildin_record_video BOOLEAN NOT NULL DEFAULT FALSE,
        buildin_stop_shortcut BOOLEAN NOT NULL DEFAULT TRUE,
        buildin_highlight_ui BOOLEAN NOT NULL DEFAULT FALSE,
        custom_prj_args TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime')),
        updated_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime'))
    );

CREATE TABLE
    task_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduler_name TEXT NULL DEFAULT NULL,
        project_source TEXT NOT NULL DEFAULT 'local' CHECK (project_source IN ('local', 'console')),
        project_id INTEGER NOT NULL,
        project_name TEXT NOT NULL,
        project_version TEXT NOT NULL,
        run_start DATETIME NOT NULL,
        run_end DATETIME NULL DEFAULT NULL,
        status TEXT NOT NULL DEFAULT 'running' CHECK (
            status IN (
                'running',
                'completed',
                'error',
                'cancel',
                'timeout'
            )
        ),
        log_path TEXT NOT NULL,
        no_log_folder BOOLEAN NOT NULL DEFAULT FALSE,
        no_log_video BOOLEAN NOT NULL DEFAULT FALSE,
        created_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime')),
        updated_at DATETIME NOT NULL DEFAULT (datetime ('now', 'localtime'))
    );

CREATE TRIGGER update_project_local_updated_at AFTER
UPDATE ON project_local FOR EACH ROW BEGIN
UPDATE project_local
SET
    updated_at=(datetime ('now', 'localtime'))
WHERE
    id=OLD.id;

END;

CREATE TRIGGER update_task_scheduler_updated_at AFTER
UPDATE ON task_scheduler FOR EACH ROW BEGIN
UPDATE task_scheduler
SET
    updated_at=(datetime ('now', 'localtime'))
WHERE
    id=OLD.id;

END;

CREATE TRIGGER update_task_history_updated_at AFTER
UPDATE ON task_history FOR EACH ROW BEGIN
UPDATE task_history
SET
    updated_at=(datetime ('now', 'localtime'))
WHERE
    id=OLD.id;

END;