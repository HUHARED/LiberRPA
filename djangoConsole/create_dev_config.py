# FileName: create_dev_config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
import secrets
from getpass import getpass
from pathlib import Path
from shutil import copyfile

from cryptography.fernet import Fernet


def _write_secret_file(secretPath: Path, secretValue: str) -> None:
    fileDescriptor = os.open(secretPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fileDescriptor, "w", encoding="utf-8") as secretFile:
        secretFile.write(secretValue)


def main() -> None:
    pathConsole = Path(__file__).resolve().parent
    pathLocal = pathConsole / ".local"
    if pathLocal.exists():
        raise FileExistsError(f"Local configuration already exists: {pathLocal}")

    databasePassword = getpass("Development database password: ")
    if not databasePassword.strip():
        raise ValueError("The development database password must not be empty.")
    smtpPassword = getpass("Development SMTP password: ")
    if not smtpPassword.strip():
        raise ValueError("The development SMTP password must not be empty.")

    pathLocal.mkdir(mode=0o700)
    pathSecrets = pathLocal / "secrets"
    pathSecrets.mkdir(mode=0o700)
    _write_secret_file(pathSecrets / "django-secret-key.txt", secrets.token_urlsafe(64))
    _write_secret_file(
        pathSecrets / "encryption-key.txt", Fernet.generate_key().decode("ascii")
    )
    _write_secret_file(pathSecrets / "database-password.txt", databasePassword)
    _write_secret_file(pathSecrets / "smtp-password.txt", smtpPassword)
    copyfile(pathConsole / "Console.example.jsonc", pathLocal / "Console.jsonc")
    print(f"Created local development configuration: {pathLocal / 'Console.jsonc'}")


if __name__ == "__main__":
    main()
