# FileName: restore_console.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import hashlib
import json
import logging
import logging.config
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import django
import psycopg
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from psycopg.conninfo import make_conninfo

_PATH_CONSOLE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PATH_CONSOLE / "backend"))

from console_project.config import DatabaseConfig, parse_config
from console_project.logging import (
    get_exception_summary,
    capture_command_errors,
    build_logging_config,
)
from console_project.recovery import (
    STR_RESTORE_PENDING_FILE,
    STR_RESTORE_READY_FILE,
    permit_restore_setup,
)
from console_project.version import STR_CONSOLE_VERSION
from operations.backup import BackupError, verify_backup

_LOGGER = logging.getLogger("console.restore")


def restore_backup(backupPath: Path, targetPath: Path, database: DatabaseConfig) -> Path:
    """Restore into a separate empty directory and an already-created empty database."""
    pathBackup = backupPath.resolve(strict=True)
    pathTarget = targetPath.resolve()
    if pathTarget == pathBackup or pathTarget.is_relative_to(pathBackup):
        raise BackupError(
            "The restore target must be separate from the backup directory."
        )
    if targetPath.is_symlink() or (pathTarget.exists() and any(pathTarget.iterdir())):
        raise BackupError("The restore target must be an empty directory.")
    if database.name in ("postgres", "template0", "template1"):
        raise BackupError("Use a separate empty Console database.")
    _LOGGER.info("Validating backup files.")
    manifest = verify_backup(pathBackup)
    if manifest.console_version != STR_CONSOLE_VERSION:
        raise BackupError("Use the Console release recorded in this backup.")
    if manifest.django_version.split(".")[:2] != django.get_version().split(".")[:2]:
        raise BackupError(
            "Use the Django major and minor version recorded in this backup."
        )
    strPassword = (
        Path(database.passwordFile)
        .resolve(strict=True)
        .read_text(encoding="utf-8-sig")
        .rstrip("\r\n")
    )
    if not strPassword.strip() or "\r" in strPassword or "\n" in strPassword:
        raise BackupError("Use a single-line database password.")
    strConnection = make_conninfo(
        host=database.host,
        port=database.port,
        dbname=database.name,
        user=database.user,
        connect_timeout=10,
    )
    strRestore = shutil.which("pg_restore")
    if strRestore is None:
        raise BackupError("pg_restore is required on PATH.")
    _LOGGER.info("Checking the PostgreSQL archive.")
    with capture_command_errors(
        _LOGGER, "pg_restore --list", secrets=(strPassword,)
    ) as intErrorDescriptor:
        subprocess.run(
            [strRestore, "--list", str(pathBackup / "database.dump")],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=intErrorDescriptor,
        )

    _LOGGER.info("Checking the target database.")
    with psycopg.connect(
        strConnection, password=strPassword, autocommit=True
    ) as databaseConnection:
        with databaseConnection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_userbyid(datdba), pg_encoding_to_char(encoding), "
                "datcollate, datctype, current_setting('server_version_num')::integer "
                "FROM pg_database WHERE datname = current_database()"
            )
            databaseInfo = cursor.fetchone()
            if databaseInfo is None or databaseInfo[0] != database.user:
                raise BackupError(
                    "The target database must belong to the configured Console role."
                )
            if tuple(databaseInfo[1:4]) != (
                manifest.database_encoding,
                manifest.database_collation,
                manifest.database_ctype,
            ):
                raise BackupError(
                    "The target database encoding and locale must match the backup."
                )
            if databaseInfo[4] // 10000 < int(manifest.postgres_version.split(".", 1)[0]):
                raise BackupError(
                    "The target PostgreSQL version is older than the backup server."
                )
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN "
                "('public', 'information_schema') AND nspname NOT LIKE 'pg_%') "
                "OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public') "
                "OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public') "
                "OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                "WHERE n.nspname='public') "
                "OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')"
            )
            if cursor.fetchone() != (False,):
                raise BackupError(
                    "The target database is not empty; no data was overwritten."
                )
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                "WHERE datname=current_database() AND pid<>pg_backend_pid())"
            )
            if cursor.fetchone() != (False,):
                raise BackupError(
                    "Stop other connections to the target database before restoring."
                )

    pathTarget.mkdir(parents=True, exist_ok=True, mode=0o700)
    pathPending = pathTarget / STR_RESTORE_PENDING_FILE
    with pathPending.open("x", encoding="ascii") as handle:
        handle.write(str(manifest.backup_id) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    def sync_directory(path: Path) -> None:
        if os.name != "nt":
            intDescriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(intDescriptor)
            finally:
                os.close(intDescriptor)

    sync_directory(pathTarget)
    pathPassword = pathTarget / ".restore.pgpass"
    try:
        _LOGGER.info("Copying backup files and configuration.")
        for entry in manifest.files:
            if entry.path.startswith("config/secrets/"):
                pathDestination = pathTarget / entry.path.removeprefix("config/")
            elif entry.path.startswith("storage/"):
                pathDestination = pathTarget / entry.path
            else:
                continue
            pathDestination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(pathBackup / entry.path, pathDestination)
            pathDestination.chmod(0o600)
            with pathDestination.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != entry.sha256:
                    raise BackupError("A restored file failed its checksum check.")
                os.fsync(handle.fileno())
            sync_directory(pathDestination.parent)
        (pathTarget / "storage").mkdir(exist_ok=True, mode=0o700)
        pathConfig = pathTarget / "Console.jsonc"
        config = parse_config(
            (pathBackup / "config/Console.jsonc").read_bytes(),
            pathBackup / "config/Console.jsonc",
        )
        dictConfig = config.model_dump(mode="json")
        dictConfig["database"] = database.model_dump(mode="json")
        dictConfig["database"]["passwordFile"] = "secrets/database-password.txt"
        dictConfig["storageRoot"] = "storage"
        dictConfig["backup"] = None
        pathDatabasePassword = pathTarget / "secrets/database-password.txt"
        pathDatabasePassword.write_text(strPassword, encoding="utf-8")
        pathDatabasePassword.chmod(0o600)
        pathConfig.write_text(json.dumps(dictConfig, indent=2) + "\n", encoding="utf-8")
        pathConfig.chmod(0o600)
        for pathFile in (pathDatabasePassword, pathConfig):
            with pathFile.open("rb") as handle:
                os.fsync(handle.fileno())
        for pathDirectory in (pathTarget / "secrets", pathTarget / "storage", pathTarget):
            sync_directory(pathDirectory)

        strPasswordLine = ":".join(
            str(value).replace("\\", "\\\\").replace(":", "\\:")
            for value in (
                database.host,
                database.port,
                database.name,
                database.user,
                strPassword,
            )
        )
        with pathPassword.open("x", encoding="utf-8") as handle:
            pathPassword.chmod(0o600)
            handle.write(strPasswordLine + "\n")
        dictEnvironment = dict(os.environ)
        for strName in ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE"):
            dictEnvironment.pop(strName, None)
        dictEnvironment["PGPASSFILE"] = str(pathPassword)
        _LOGGER.info("Restoring the database.")
        with capture_command_errors(
            _LOGGER, "pg_restore", secrets=(strPassword,)
        ) as intErrorDescriptor:
            subprocess.run(
                [
                    strRestore,
                    "--single-transaction",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname",
                    strConnection,
                    str(pathBackup / "database.dump"),
                ],
                env=dictEnvironment,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=intErrorDescriptor,
            )

        _LOGGER.info("Validating and preparing the restored database.")
        os.environ["LIBERRPA_CONSOLE_CONFIG"] = str(pathConfig)
        os.environ["DJANGO_SETTINGS_MODULE"] = "console_project.settings"
        with permit_restore_setup():
            django.setup()
        from operations.restore import (
            validate_restored_schema,
            sanitize_restored_database,
        )

        validate_restored_schema(manifest)
        sanitize_restored_database(manifest, datetime.now(UTC))
        _LOGGER.info("Finalizing the restored instance.")
        pathPending.replace(pathTarget / STR_RESTORE_READY_FILE)
        sync_directory(pathTarget)
        return pathConfig
    finally:
        pathPassword.unlink(missing_ok=True)


def main() -> None:
    logging.config.dictConfig(build_logging_config("INFO"))
    parser = argparse.ArgumentParser(
        description=(
            "Restore a trusted Console backup after stopping the old Console instance and all its workers. "
            "The target directory and target database must be empty."
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--database-host", required=True)
    parser.add_argument("--database-port", type=int, default=5432)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--database-user", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        database = DatabaseConfig(
            host=args.database_host,
            port=args.database_port,
            name=args.database_name,
            user=args.database_user,
            passwordFile=str(args.password_file),
        )
        pathConfig = restore_backup(args.backup, args.target, database)
    except (BackupError, ImproperlyConfigured) as e:
        _LOGGER.error("Restore stopped: %s", str(e)[:2000], exc_info=True)
        parser.exit(
            1,
            "Keep the target isolated; any restore.pending marker must remain in place.\n",
        )
    except (
        OSError,
        ValueError,
        DatabaseError,
        psycopg.Error,
        subprocess.CalledProcessError,
    ) as e:
        _LOGGER.exception("Restore stopped.")
        parser.exit(
            1,
            f"Restore stopped: {get_exception_summary(e)}. "
            "Keep the target isolated; any restore.pending marker must remain in place.\n",
        )
    except KeyboardInterrupt:
        parser.exit(
            1,
            "Restore cancelled. Keep the target isolated and preserve any restore.pending marker.\n",
        )
    print(f"Restore completed in maintenance mode. Configuration: {pathConfig}")
    print(
        "Review restored permissions and settings, then run 'python backend/manage.py maintenance resume' from the Console directory. "
        "Backups remain disabled."
    )


if __name__ == "__main__":
    main()
