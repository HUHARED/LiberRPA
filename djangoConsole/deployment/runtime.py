# FileName: runtime.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import os
import pwd
import secrets
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet

_PATH_APP = Path("/app")
_PATH_DATA = Path("/data")
_PATH_CONFIG = _PATH_DATA / "config/Console.jsonc"
_PATH_POSTGRES = _PATH_DATA / "postgres"
_PATH_DEPLOYMENT = _PATH_APP / "deployment"


def run_as(
    user: str,
    command: list[str],
    *,
    inputText: str | None = None,
    hideOutput: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["runuser", "-u", user, "--", *command],
        check=True,
        input=inputText,
        text=True,
        capture_output=hideOutput,
    )


def prepare_runtime_directories() -> None:
    for strPath, strUser, intMode in (
        ("/run/liberrpa", "root", 0o755),
        ("/run/liberrpa/web", "liberrpa", 0o700),
        ("/run/postgresql", "postgres", 0o755),
    ):
        path = Path(strPath)
        path.mkdir(parents=True, exist_ok=True)
        user = pwd.getpwnam(strUser)
        os.chown(path, user.pw_uid, user.pw_gid)
        path.chmod(intMode)


def prepare_empty_data() -> None:
    if not _PATH_DATA.is_dir() or any(_PATH_DATA.iterdir()):
        raise RuntimeError("Initialization requires an existing, empty /data mount.")
    _PATH_DATA.chmod(0o755)
    for strName, strUser in (
        ("config", "liberrpa"),
        ("secrets", "liberrpa"),
        ("storage", "liberrpa"),
        ("postgres", "postgres"),
    ):
        path = _PATH_DATA / strName
        path.mkdir(mode=0o700)
        user = pwd.getpwnam(strUser)
        os.chown(path, user.pw_uid, user.pw_gid)
    if Path("/backup").is_dir():
        user = pwd.getpwnam("liberrpa")
        os.chown("/backup", user.pw_uid, user.pw_gid)
        Path("/backup").chmod(0o700)


def write_new_file(path: Path, content: bytes) -> None:
    intDescriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(intDescriptor, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    user = pwd.getpwnam("liberrpa")
    os.chown(path, user.pw_uid, user.pw_gid)


def check_postgres_directory() -> None:
    if (_PATH_POSTGRES / "PG_VERSION").read_text().strip() != "17":
        raise RuntimeError(
            "This image requires an existing PostgreSQL 17 data directory."
        )


@contextmanager
def temporary_postgres() -> Generator[None]:
    check_postgres_directory()
    # pg_ctl refuses an already running cluster; offline commands cannot share production data.
    run_as(
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
        run_as(
            "postgres", ["pg_ctl", "-D", str(_PATH_POSTGRES), "-m", "fast", "-w", "stop"]
        )


def create_database(
    password: str,
    *,
    encoding: str = "UTF8",
    collation: str = "C.UTF-8",
    ctype: str = "C.UTF-8",
) -> None:
    run_as(
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
    with temporary_postgres():
        run_as(
            "postgres",
            ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
            inputText=strSql,
            hideOutput=True,
        )


def initialize(configPath: Path, smtpPasswordPath: Path) -> None:
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
        raise RuntimeError(
            "Use the paths in Console.container.example.jsonc for initialization."
        )
    if (
        config.database.host,
        config.database.port,
        config.database.name,
        config.database.user,
    ) != ("127.0.0.1", 5432, "liberrpa_console", "liberrpa_console"):
        raise RuntimeError(
            "Use the internal database settings from the container template."
        )
    if config.fileTransferProxy is None or (
        config.fileTransferProxy.host,
        config.fileTransferProxy.port,
    ) != ("127.0.0.1", 9999):
        raise RuntimeError("The container requires its local file transfer proxy.")
    smtpPassword = smtpPasswordPath.read_bytes()
    if not smtpPassword.decode("utf-8-sig").rstrip("\r\n").strip():
        raise RuntimeError("The SMTP password file must not be empty.")
    prepare_empty_data()
    password = secrets.token_urlsafe(48)
    write_new_file(_PATH_CONFIG, configBytes)
    for strName, value in (
        ("django-secret-key.txt", secrets.token_urlsafe(64).encode()),
        ("encryption-key.txt", Fernet.generate_key()),
        ("database-password.txt", password.encode()),
        ("smtp-password.txt", smtpPassword),
    ):
        write_new_file(_PATH_DATA / "secrets" / strName, value)
    create_database(password)
    with temporary_postgres():
        # Published migrations must already describe the models; this check writes no migration files.
        run_as(
            "liberrpa",
            [
                "python",
                "/app/backend/manage.py",
                "makemigrations",
                "--check",
                "--dry-run",
                "--noinput",
            ],
        )
        run_as("liberrpa", ["python", "/app/backend/manage.py", "migrate", "--noinput"])
        run_as("liberrpa", ["python", "/app/backend/manage.py", "initialize_console"])
    print(
        "Console initialized. Keep /data and its secrets together when backing up or moving the instance."
    )


def run_application(command: list[str]) -> None:
    import django
    from django.core.management import call_command
    from django.db import OperationalError, connection
    from django.db.migrations.executor import MigrationExecutor

    django.setup()
    floatDeadline = time.monotonic() + 60
    while True:
        try:
            connection.ensure_connection()
            break
        except OperationalError:
            if time.monotonic() >= floatDeadline:
                raise RuntimeError(
                    "PostgreSQL did not become ready within 60 seconds."
                ) from None
            time.sleep(1)
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError(
            "Database migrations are pending. Apply published migrations while the service is stopped."
        )
    # This read-only comparison rejects builds that omitted required migration files.
    call_command(
        "makemigrations", check=True, dry_run=True, interactive=False, verbosity=0
    )
    from accounts.models import STR_PLATFORM_ADMIN_LOGIN, User
    from django.conf import settings

    if not User.objects.filter(
        is_platform_admin=True, platform_login=STR_PLATFORM_ADMIN_LOGIN
    ).exists():
        raise RuntimeError(
            "The platform administrator is missing. Explicit initialization or recovery is required."
        )
    pathStorage = Path(settings.CONSOLE_STORAGE_ROOT)
    if not pathStorage.is_dir() or not os.access(
        pathStorage, os.R_OK | os.W_OK | os.X_OK
    ):
        raise RuntimeError("The configured storage directory is missing or inaccessible.")
    connection.close()
    os.execvp(command[0], command)


def check_health() -> None:
    from console_project.config import read_config_snapshot

    snapshot = read_config_snapshot(_PATH_CONFIG)
    request = Request(
        "http://127.0.0.1:52100/api/health/database/",
        headers={
            "Host": urlsplit(str(snapshot.config.consoleUrl)).netloc,
            "X-Forwarded-For": "127.0.0.1",
        },
    )
    with urlopen(request, timeout=3) as response:
        if response.status != 200:
            raise RuntimeError("Console is not ready.")


def main() -> None:
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
        check_health()
        return
    if args.action == "run":
        if not args.command:
            parser.error("A child command is required.")
        run_application(args.command)
        return
    if os.geteuid() != 0:
        raise RuntimeError(
            "Use the container entry point as root; child services run under their own users."
        )
    prepare_runtime_directories()
    if args.action == "initialize":
        initialize(args.config, args.smtp_password_file)
    elif args.action == "prepare-restore":
        password = args.password_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
        if not password.strip():
            raise RuntimeError("The database password file must not be empty.")
        prepare_empty_data()
        create_database(
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
        with temporary_postgres():
            run_as("liberrpa", args.command)
    else:
        from console_project.config import read_config_snapshot
        from console_project.recovery import require_completed_restore

        check_postgres_directory()
        require_completed_restore(_PATH_CONFIG)
        read_config_snapshot(_PATH_CONFIG)
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
    except subprocess.CalledProcessError:
        print(
            "A deployment command failed. Review its preceding diagnostics and preserved data before retrying.",
            file=sys.stderr,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        print("Deployment command cancelled.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)
