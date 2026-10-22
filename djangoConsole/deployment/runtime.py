# FileName: runtime.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import logging
import logging.config
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from console_project.logging import (
    get_exception_summary,
    capture_command_errors,
    build_logging_config,
)

_LOGGER = logging.getLogger("console.deployment")

_PATH_APP = Path("/app")
_PATH_DATA = Path("/data")
_PATH_CONFIG = _PATH_DATA / "config/Console.jsonc"
_PATH_POSTGRES = _PATH_DATA / "postgres"
_PATH_DEPLOYMENT = _PATH_APP / "deployment"


class DeploymentError(RuntimeError):
    """A controlled deployment failure that can be shown without exposing credentials."""


def _run_as(
    user: str,
    command: list[str],
    *,
    inputText: str | None = None,
    hideOutput: bool = False,
    secretValues: Iterable[str] = (),
) -> subprocess.CompletedProcess[str]:
    _LOGGER.info("Running deployment command: %s.", Path(command[0]).name)
    if hideOutput:
        with capture_command_errors(
            _LOGGER, Path(command[0]).name, secrets=secretValues
        ) as intErrorDescriptor:
            return subprocess.run(
                ["runuser", "-u", user, "--", *command],
                check=True,
                input=inputText,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=intErrorDescriptor,
            )
    return subprocess.run(
        ["runuser", "-u", user, "--", *command],
        check=True,
        input=inputText,
        text=True,
    )


def _set_owner(path: Path, user: str) -> None:
    """Set the owner and primary group of a Linux deployment path."""
    if sys.platform == "linux":
        import pwd

        userInfo = pwd.getpwnam(user)
        os.chown(path, userInfo.pw_uid, userInfo.pw_gid)
    else:
        raise DeploymentError("Container deployment commands require Linux.")


def _prepare_runtime_directories() -> None:
    for strPath, strUser, intMode in (
        ("/run/liberrpa", "root", 0o755),
        ("/run/liberrpa/web", "liberrpa", 0o700),
        ("/run/postgresql", "postgres", 0o755),
    ):
        path = Path(strPath)
        path.mkdir(parents=True, exist_ok=True)
        _set_owner(path, strUser)
        path.chmod(intMode)


def _prepare_empty_data() -> None:
    if not _PATH_DATA.is_dir() or any(_PATH_DATA.iterdir()):
        raise DeploymentError("Initialization requires an existing, empty /data mount.")
    _PATH_DATA.chmod(0o755)
    for strName, strUser in (
        ("config", "liberrpa"),
        ("secrets", "liberrpa"),
        ("storage", "liberrpa"),
        ("postgres", "postgres"),
    ):
        path = _PATH_DATA / strName
        path.mkdir(mode=0o700)
        _set_owner(path, strUser)
    if Path("/backup").is_dir():
        _set_owner(Path("/backup"), "liberrpa")
        Path("/backup").chmod(0o700)


def _write_new_file(path: Path, content: bytes) -> None:
    intDescriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(intDescriptor, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    _set_owner(path, "liberrpa")


def _check_postgres_directory() -> None:
    if (_PATH_POSTGRES / "PG_VERSION").read_text().strip() != "17":
        raise DeploymentError(
            "This image requires an existing PostgreSQL 17 data directory."
        )


@contextmanager
def _temporary_postgres() -> Generator[None]:
    _check_postgres_directory()
    # pg_ctl refuses an already running cluster; offline commands cannot share production data.
    _run_as(
        "postgres",
        [
            "pg_ctl",
            "-D",
            str(_PATH_POSTGRES),
            "-l",
            "/run/postgresql/startup.log",
            "-w",
            "start",
        ],
    )
    try:
        yield
    finally:
        _run_as(
            "postgres", ["pg_ctl", "-D", str(_PATH_POSTGRES), "-m", "fast", "-w", "stop"]
        )


def _create_database(
    password: str,
    *,
    encoding: str = "UTF8",
    collation: str = "C.UTF-8",
    ctype: str = "C.UTF-8",
) -> None:
    _run_as(
        "postgres",
        [
            "initdb",
            "-D",
            str(_PATH_POSTGRES),
            "--username=postgres",
            "--auth-local=peer",
            "--auth-host=reject",
            "--encoding=UTF8",
            "--locale=C.UTF-8",
            "--data-checksums",
        ],
    )
    with (_PATH_POSTGRES / "postgresql.conf").open("a", encoding="utf-8") as file:
        file.write(
            "\nlisten_addresses = '127.0.0.1'\nport = 5432\nunix_socket_directories = '/run/postgresql'\npassword_encryption = 'scram-sha-256'\ntimezone = 'UTC'\n"
        )
    (_PATH_POSTGRES / "pg_hba.conf").write_text(
        "local all postgres peer\n"
        "host liberrpa_console liberrpa_console 127.0.0.1/32 scram-sha-256\n",
        encoding="utf-8",
    )
    # Password bytes go through stdin, never a process argument, environment variable, or log.
    from psycopg import sql

    strSql = (
        sql
        .SQL(
            "CREATE ROLE liberrpa_console LOGIN PASSWORD {};\n"
            "CREATE DATABASE liberrpa_console OWNER liberrpa_console TEMPLATE template0 "
            "ENCODING {} LC_COLLATE {} LC_CTYPE {};\n"
        )
        .format(*(sql.Literal(value) for value in (password, encoding, collation, ctype)))
        .as_string()
    )
    with _temporary_postgres():
        _run_as(
            "postgres",
            ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
            inputText=strSql,
            hideOutput=True,
            secretValues=(password,),
        )


def _check_release_migrations() -> None:
    """Check packaged model definitions without waiting for or changing the database."""
    import django
    from django.apps import apps
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.exceptions import (
        BadMigrationError,
        CircularDependencyError,
        NodeNotFoundError,
    )
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState

    _LOGGER.info("Checking published migrations.")
    django.setup()
    try:
        loader = MigrationLoader(None, ignore_no_migrations=True)
    except (
        BadMigrationError,
        CircularDependencyError,
        NodeNotFoundError,
        ValueError,
    ) as e:
        raise DeploymentError(
            "Published migrations are missing or invalid. "
            "Generate and include the complete migration files before deployment."
        ) from e

    listMissingApp = sorted(
        appConfig.label
        for appConfig in apps.get_app_configs()
        if appConfig.label in loader.unmigrated_apps and any(appConfig.get_models())
    )
    if listMissingApp:
        raise DeploymentError(
            "Published migrations are missing for: " + ", ".join(listMissingApp) + "."
        )
    if dictConflict := loader.detect_conflicts():
        raise DeploymentError(
            "Published migrations have conflicting branches in: "
            + ", ".join(sorted(dictConflict))
            + ". Resolve them before deployment."
        )
    dictChange = MigrationAutodetector(
        loader.project_state(), ProjectState.from_apps(apps)
    ).changes(graph=loader.graph)
    if dictChange:
        raise DeploymentError(
            "Model changes are missing published migrations for: "
            + ", ".join(sorted(dictChange))
            + ". Generate and include them before deployment."
        )


def _initialize(configPath: Path, smtpPasswordPath: Path) -> None:
    from console_project.config import parse_config

    configBytes = configPath.read_bytes()
    config = parse_config(configBytes, configPath)
    expectedPaths = (
        (config.secretKeyFile, "../secrets/django-secret-key.txt"),
        (config.database.passwordFile, "../secrets/database-password.txt"),
        (config.smtp.passwordFile, "../secrets/smtp-password.txt"),
        (config.storageRoot, "../storage"),
    )
    if any(
        actual != expected for actual, expected in expectedPaths
    ) or config.encryptionKeyFiles != ["../secrets/encryption-key.txt"]:
        raise DeploymentError(
            "Use the paths in Console.container.example.jsonc for initialization."
        )
    if (
        config.database.host,
        config.database.port,
        config.database.name,
        config.database.user,
    ) != ("127.0.0.1", 5432, "liberrpa_console", "liberrpa_console"):
        raise DeploymentError(
            "Use the internal database settings from the container template."
        )
    if config.fileTransferProxy is None or (
        config.fileTransferProxy.host,
        config.fileTransferProxy.port,
    ) != ("127.0.0.1", 9999):
        raise DeploymentError("The container requires its local file transfer proxy.")
    smtpPassword = smtpPasswordPath.read_bytes()
    if not smtpPassword.decode("utf-8-sig").rstrip("\r\n").strip():
        raise DeploymentError("The SMTP password file must not be empty.")
    _prepare_empty_data()
    password = secrets.token_urlsafe(48)
    _write_new_file(_PATH_CONFIG, configBytes)
    for strName, value in (
        ("django-secret-key.txt", secrets.token_urlsafe(64).encode()),
        ("encryption-key.txt", Fernet.generate_key()),
        ("database-password.txt", password.encode()),
        ("smtp-password.txt", smtpPassword),
    ):
        _write_new_file(_PATH_DATA / "secrets" / strName, value)
    _check_release_migrations()
    _create_database(password)
    with _temporary_postgres():
        _LOGGER.info("Applying database migrations.")
        _run_as("liberrpa", ["python", "/app/backend/manage.py", "migrate", "--noinput"])
        _LOGGER.info("Creating the platform administrator.")
        _run_as("liberrpa", ["python", "/app/backend/manage.py", "initialize_console"])
    print(
        "Console initialized. Keep /data and its secrets together when backing up or moving the instance."
    )


def _run_application(command: list[str]) -> None:
    import django
    from django.db import OperationalError, connection
    from django.db.migrations.exceptions import InconsistentMigrationHistory
    from django.db.migrations.executor import MigrationExecutor

    django.setup()
    floatDeadline = time.monotonic() + 60
    while True:
        try:
            connection.ensure_connection()
            break
        except OperationalError:
            if time.monotonic() >= floatDeadline:
                raise DeploymentError(
                    "PostgreSQL did not become ready within 60 seconds."
                )
            time.sleep(1)
    executor = MigrationExecutor(connection)
    try:
        executor.loader.check_consistent_history(connection)
    except InconsistentMigrationHistory as e:
        raise DeploymentError(
            "Database migration history is inconsistent. "
            "Resolve it before starting the service."
        ) from e
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise DeploymentError(
            "Database migrations are pending. Apply published migrations while the service is stopped."
        )
    from accounts.models import STR_PLATFORM_ADMIN_LOGIN, User
    from django.conf import settings

    if not User.objects.filter(
        is_platform_admin=True, platform_login=STR_PLATFORM_ADMIN_LOGIN
    ).exists():
        raise DeploymentError(
            "The platform administrator is missing. Explicit initialization or recovery is required."
        )
    pathStorage = Path(settings.CONSOLE_STORAGE_ROOT)
    if not pathStorage.is_dir() or not os.access(
        pathStorage, os.R_OK | os.W_OK | os.X_OK
    ):
        raise DeploymentError(
            "The configured storage directory is missing or inaccessible."
        )
    connection.close()
    os.execvp(command[0], command)


def _check_health() -> None:
    # Keep the proxy, running application and database in the probe; never reread pending configuration.
    connection = HTTPConnection("127.0.0.1", 52100, timeout=3)
    try:
        connection.request(
            "GET",
            "/api/health/database/",
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise DeploymentError(
                f"Console readiness check returned HTTP {response.status}."
            )
    finally:
        connection.close()


def main() -> None:
    logging.config.dictConfig(build_logging_config("INFO"))
    if sys.platform == "linux":
        intEffectiveUserId = os.geteuid()
    else:
        raise DeploymentError("Container deployment commands require Linux.")
    parser = argparse.ArgumentParser(
        description="Explicit container initialization, offline maintenance, and ordinary startup."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    initializer = subparsers.add_parser("initialize")
    initializer.add_argument("--config", type=Path, required=True)
    initializer.add_argument("--smtp-password-file", type=Path, required=True)
    restore = subparsers.add_parser("prepare-restore")
    restore.add_argument("--password-file", type=Path, required=True)
    restore.add_argument("--database-encoding", default="UTF8")
    restore.add_argument("--database-collation", default="C.UTF-8")
    restore.add_argument("--database-ctype", default="C.UTF-8")
    offline = subparsers.add_parser("offline")
    offline.add_argument("command", nargs=argparse.REMAINDER)
    application = subparsers.add_parser("run")
    application.add_argument("command", nargs=argparse.REMAINDER)
    subparsers.add_parser("serve")
    subparsers.add_parser("health")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "health":
        _check_health()
        return
    _LOGGER.info("Deployment action: %s.", args.action)
    if args.action == "run":
        if not args.command:
            parser.error("A child command is required.")
        _run_application(args.command)
        return
    if intEffectiveUserId != 0:
        raise DeploymentError(
            "Use the container entry point as root; child services run under their own users."
        )
    _prepare_runtime_directories()
    if args.action == "initialize":
        _initialize(args.config, args.smtp_password_file)
    elif args.action == "prepare-restore":
        password = args.password_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
        if not password.strip():
            raise DeploymentError("The database password file must not be empty.")
        _prepare_empty_data()
        _create_database(
            password,
            encoding=args.database_encoding,
            collation=args.database_collation,
            ctype=args.database_ctype,
        )
        print(
            "Empty recovery database created. Restore into /data/config before starting the service."
        )
    elif args.action == "offline":
        if not args.command:
            parser.error("An offline command is required.")
        with _temporary_postgres():
            _run_as("liberrpa", args.command)
    else:
        from console_project.recovery import require_completed_restore

        _check_postgres_directory()
        require_completed_restore(_PATH_CONFIG)
        _check_release_migrations()
        subprocess.run(
            ["haproxy", "-c", "-f", str(_PATH_DEPLOYMENT / "haproxy.cfg")], check=True
        )
        os.execvp(
            "supervisord",
            ["supervisord", "-c", str(_PATH_DEPLOYMENT / "supervisord.conf")],
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        _LOGGER.exception("Deployment command failed.")
        print(
            f"Deployment stopped: {get_exception_summary(e)}. "
            "Review the diagnostics and preserved data before retrying.",
            file=sys.stderr,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        print("Deployment command cancelled.", file=sys.stderr)
        sys.exit(1)
    except (DeploymentError, ImproperlyConfigured) as e:
        _LOGGER.error("Deployment stopped: %s", str(e)[:2000], exc_info=True)
        sys.exit(1)
    except Exception:
        _LOGGER.exception("Deployment failed.")
        sys.exit(1)
