# FileName: backup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, cast

import django
import psycopg
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from console_project.config import ConsoleConfigSnapshot, parse_config, read_config_snapshot
from console_project.local_locks import hold_local_lock
from console_project.version import STR_CONSOLE_VERSION

from .backup_contracts import BackupStage

_LOGGER = logging.getLogger("console.backup")


class BackupError(Exception):
    """A controlled backup failure suitable for the platform status page."""


class BackupFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    path: str
    size_bytes: int = Field(ge=0)
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or path.is_absolute()
            or any(part in ("", ".", "..") for part in value.split("/"))
            or ":" in value
        ):
            raise ValueError(
                "Backup member paths must be relative paths without parent traversal."
            )
        return value


class BackupRole(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    login: bool
    superuser: bool
    create_db: bool
    create_role: bool
    inherit: bool
    replication: bool
    bypass_rls: bool


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    format_version: Literal[1] = 1
    backup_id: uuid.UUID
    data_as_of: AwareDatetime
    console_version: str
    python_version: str
    django_version: str
    postgres_version: str
    database_name: str
    database_user: str
    database_encoding: str
    database_collation: str
    database_ctype: str
    role: BackupRole
    migrations: list[tuple[str, str]]
    blob_ids: list[uuid.UUID]
    files: list[BackupFile]

    @model_validator(mode="after")
    def validate_members(self) -> "BackupManifest":
        listPath = [entry.path for entry in self.files]
        if len(listPath) != len(set(listPath)) or len(self.blob_ids) != len(
            set(self.blob_ids)
        ):
            raise ValueError("Backup members must be unique.")
        setRequired = {"database.dump", "config/Console.jsonc"}
        setBlobPath = {f"storage/{blobId.hex[:2]}/{blobId.hex}" for blobId in self.blob_ids}
        if not setRequired.issubset(listPath):
            raise ValueError("Backup database and configuration are required.")
        if {value for value in listPath if value.startswith("storage/")} != setBlobPath:
            raise ValueError("The backup file list does not match its stored files.")
        if any(
            value not in setRequired
            and value not in setBlobPath
            and not value.startswith("config/secrets/")
            for value in listPath
        ):
            raise ValueError("The backup contains an unsupported member.")
        return self


@dataclass(frozen=True)
class BackupResult:
    directoryName: str
    dataAsOf: datetime
    sizeBytes: int


def verify_backup(path: Path) -> BackupManifest:
    """Validate a complete bundle without connecting to or configuring Django's database."""
    try:
        pathManifest = path / "manifest.json"
        if pathManifest.is_symlink() or not pathManifest.resolve().is_relative_to(
            path.resolve()
        ):
            raise BackupError("The backup manifest is outside the backup directory.")
        manifest = BackupManifest.model_validate_json(pathManifest.read_bytes())
        for entry in manifest.files:
            pathFile = path / entry.path
            if (
                not pathFile.resolve().is_relative_to(path.resolve())
                or pathFile.is_symlink()
                or not pathFile.is_file()
            ):
                raise BackupError(
                    "A required backup file is missing or is not a regular file."
                )
            if pathFile.stat().st_size != entry.size_bytes:
                raise BackupError("A backup file has an unexpected size.")
            with pathFile.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != entry.sha256:
                    raise BackupError("A backup file failed its checksum check.")
        pathConfig = path / "config/Console.jsonc"
        config = parse_config(pathConfig.read_bytes(), pathConfig)
        setMember = {entry.path for entry in manifest.files}
        for strSecretFile in (
            config.secretKeyFile,
            config.database.passwordFile,
            config.smtp.passwordFile,
            *config.encryptionKeyFiles,
        ):
            if (
                PurePosixPath(strSecretFile).is_absolute()
                or ".." in PurePosixPath(strSecretFile).parts
                or f"config/{strSecretFile}" not in setMember
            ):
                raise BackupError(
                    "The backup configuration refers to a missing secret file."
                )
        return manifest
    except (OSError, ValueError, ValidationError, ImproperlyConfigured) as e:
        raise BackupError("The backup could not be read or did not pass validation.") from e


def create_backup(
    backupId: uuid.UUID,
    *,
    reportStage: Callable[[BackupStage, datetime | None], None],
) -> BackupResult:
    """Export one database snapshot and copy the immutable files named by that snapshot."""
    from file_storage.models import StoredBlobState
    from file_storage.services import sync_directory

    snapshot = cast(ConsoleConfigSnapshot, settings.CONSOLE_CONFIG_SNAPSHOT)
    config = snapshot.config
    backupConfig = config.backup
    if backupConfig is None:
        raise BackupError("Backups are not configured.")
    pathRoot = (snapshot.configPath.parent / backupConfig.location).resolve()
    pathStorage = Path(settings.CONSOLE_STORAGE_ROOT).resolve()
    pathConfigDirectory = snapshot.configPath.parent.resolve()
    if (
        pathRoot == pathStorage
        or pathRoot.is_relative_to(pathStorage)
        or pathStorage.is_relative_to(pathRoot)
        or pathRoot == pathConfigDirectory
        or pathRoot.is_relative_to(pathConfigDirectory)
        or pathConfigDirectory.is_relative_to(pathRoot)
    ):
        raise BackupError(
            "The backup location must be separate from storage and configuration directories."
        )
    if not pathStorage.is_dir():
        raise BackupError("The file storage directory is unavailable.")
    if read_config_snapshot(snapshot.configPath) != snapshot:
        raise BackupError(
            "Configuration or secret files changed. Restart Console before creating a backup."
        )
    pathRoot.mkdir(parents=True, exist_ok=True, mode=0o700)
    pathPartial = pathRoot / f"{backupId.hex}.partial"
    pathComplete = pathRoot / backupId.hex
    if pathPartial.exists() or pathComplete.exists():
        raise BackupError("A backup with this identifier already exists.")
    pathPartial.mkdir(mode=0o700)
    listFile: list[BackupFile] = []

    def describe_file(relativePath: str) -> BackupFile:
        pathFile = pathPartial / relativePath
        with pathFile.open("rb") as handle:
            strDigest = hashlib.file_digest(handle, "sha256").hexdigest()
        return BackupFile(
            path=relativePath, size_bytes=pathFile.stat().st_size, sha256=strDigest
        )

    def write_bytes(relativePath: str, content: bytes) -> None:
        pathFile = pathPartial / relativePath
        pathFile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with pathFile.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        listFile.append(describe_file(relativePath))

    try:
        with hold_local_lock(pathStorage / ".backup.lock", wait=True):
            reportStage(BackupStage.SNAPSHOT, None)
            dictConfig = config.model_dump(mode="json")
            dictConfig["secretKeyFile"] = "secrets/django-secret-key.txt"
            dictConfig["database"]["passwordFile"] = "secrets/database-password.txt"
            dictConfig["smtp"]["passwordFile"] = "secrets/smtp-password.txt"
            dictConfig["encryptionKeyFiles"] = [
                f"secrets/encryption-{intIndex}.txt"
                for intIndex in range(len(config.encryptionKeyFiles))
            ]
            dictConfig["storageRoot"] = "../storage"
            write_bytes(
                "config/Console.jsonc",
                (json.dumps(dictConfig, indent=2) + "\n").encode("utf-8"),
            )
            for strFileName, strSource in (
                ("django-secret-key.txt", config.secretKeyFile),
                ("database-password.txt", config.database.passwordFile),
                ("smtp-password.txt", config.smtp.passwordFile),
                *(
                    (f"encryption-{intIndex}.txt", strName)
                    for intIndex, strName in enumerate(config.encryptionKeyFiles)
                ),
            ):
                write_bytes(f"config/secrets/{strFileName}", snapshot.secrets[strSource])

            strPassword = snapshot.read_secret(config.database.passwordFile)
            dictConnection = {
                "host": config.database.host,
                "port": config.database.port,
                "dbname": config.database.name,
                "user": config.database.user,
                "password": strPassword,
                "connect_timeout": 3,
            }
            with psycopg.connect(**dictConnection) as database:
                database.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                snapshotRow = database.execute(
                    "SELECT pg_export_snapshot(), transaction_timestamp()"
                ).fetchone()
                if snapshotRow is None:
                    raise BackupError("The database snapshot could not be created.")
                strSnapshotId, dataAsOf = snapshotRow
                listBlob = database.execute(
                    "SELECT id, size_bytes, sha256 FROM file_storage_storedblob WHERE state = %s ORDER BY id",
                    [StoredBlobState.AVAILABLE],
                ).fetchall()
                databaseRow = database.execute(
                    "SELECT pg_encoding_to_char(encoding), datcollate, datctype FROM pg_database WHERE datname = current_database()"
                ).fetchone()
                roleRow = database.execute(
                    "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                ).fetchone()
                if databaseRow is None or roleRow is None:
                    raise BackupError("Database recovery metadata could not be read.")
                listMigration = database.execute(
                    "SELECT app, name FROM django_migrations ORDER BY app, name"
                ).fetchall()
                postgresRow = database.execute("SHOW server_version").fetchone()
                if postgresRow is None:
                    raise BackupError("The PostgreSQL version is unavailable.")
                dictMetadata = {
                    "backup_id": backupId,
                    "data_as_of": dataAsOf,
                    "console_version": STR_CONSOLE_VERSION,
                    "python_version": platform.python_version(),
                    "django_version": django.get_version(),
                    "postgres_version": postgresRow[0],
                    "database_name": config.database.name,
                    "database_user": config.database.user,
                    "database_encoding": databaseRow[0],
                    "database_collation": databaseRow[1],
                    "database_ctype": databaseRow[2],
                    "role": BackupRole(
                        **dict(zip(BackupRole.model_fields, roleRow, strict=True))
                    ),
                    "migrations": listMigration,
                    "blob_ids": [blobId for blobId, _, _ in listBlob],
                }
                reportStage(BackupStage.DATABASE, dataAsOf)
                pathPassfile = pathPartial / ".pgpass"
                strPassline = (
                    ":".join(
                        str(value).replace("\\", "\\\\").replace(":", "\\:")
                        for value in (
                            config.database.host,
                            config.database.port,
                            config.database.name,
                            config.database.user,
                            strPassword,
                        )
                    )
                    + "\n"
                )
                intDescriptor = os.open(
                    pathPassfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(
                    intDescriptor, "w", encoding="utf-8", newline="\n"
                ) as handle:
                    handle.write(strPassline)
                dictEnvironment = {
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith("PG")
                }
                dictEnvironment["PGPASSFILE"] = str(pathPassfile)
                try:
                    result = subprocess.run(
                        [
                            "pg_dump",
                            "--format=custom",
                            "--no-password",
                            "--no-acl",
                            f"--host={config.database.host}",
                            f"--port={config.database.port}",
                            f"--username={config.database.user}",
                            f"--dbname={config.database.name}",
                            f"--snapshot={strSnapshotId}",
                            f"--file={pathPartial / 'database.dump'}",
                        ],
                        env=dictEnvironment,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                except FileNotFoundError:
                    raise BackupError(
                        "The PostgreSQL pg_dump program is unavailable."
                    ) from None
                finally:
                    pathPassfile.unlink(missing_ok=True)
                if result.returncode != 0:
                    raise BackupError("PostgreSQL could not export the database.")
            with (pathPartial / "database.dump").open("rb") as handle:
                os.fsync(handle.fileno())
            listFile.append(describe_file("database.dump"))
            reportStage(BackupStage.FILES, dataAsOf)
            for blobId, intSize, strDigest in listBlob:
                strRelativePath = f"storage/{blobId.hex[:2]}/{blobId.hex}"
                pathDestination = pathPartial / strRelativePath
                pathDestination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with (pathStorage / blobId.hex[:2] / blobId.hex).open("rb") as source:
                    with pathDestination.open("xb") as destination:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
                        destination.flush()
                        os.fsync(destination.fileno())
                listFile.append(
                    BackupFile(path=strRelativePath, size_bytes=intSize, sha256=strDigest)
                )
            manifest = BackupManifest.model_validate({**dictMetadata, "files": listFile})
            pathManifest = pathPartial / "manifest.json"
            with pathManifest.open("xb") as handle:
                handle.write((manifest.model_dump_json(indent=2) + "\n").encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            reportStage(BackupStage.VERIFYING, dataAsOf)
            verify_backup(pathPartial)
            reportStage(BackupStage.FINALIZING, dataAsOf)
            for pathDirectory in sorted(
                (entry for entry in pathPartial.rglob("*") if entry.is_dir()), reverse=True
            ):
                sync_directory(pathDirectory)
            sync_directory(pathPartial)
            pathPartial.rename(pathComplete)
            sync_directory(pathRoot)
            return BackupResult(
                directoryName=backupId.hex,
                dataAsOf=dataAsOf,
                sizeBytes=sum(entry.size_bytes for entry in listFile)
                + (pathComplete / "manifest.json").stat().st_size,
            )
    except BaseException:
        try:
            if pathPartial.exists():
                shutil.rmtree(pathPartial)
        except OSError as e:
            _LOGGER.warning(
                "Could not remove incomplete backup files: %s", type(e).__name__
            )
        raise
