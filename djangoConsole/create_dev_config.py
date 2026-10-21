# FileName: create_dev_config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import sys
from pathlib import Path
import json
import re
import os
import secrets

from pydantic import BaseModel, TypeAdapter, ValidationError
from cryptography.fernet import Fernet

_PATH_CONSOLE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PATH_CONSOLE / "backend"))

from console_project.config import (
    EmailAddress,
    DatabaseConfig,
    SmtpConfig,
    ConsoleConfig,
    parse_config,
)
from console_project.terminal import PasswordInputError, read_password


def main() -> None:
    def _prompt_config_field(
        configClass: type[BaseModel],
        fieldName: str,
        label: str,
        defaultValue: str | int | None = None,
    ) -> str | int:
        fieldInfo = configClass.model_fields[fieldName]
        valueAdapter: TypeAdapter[str | int] = TypeAdapter(fieldInfo.rebuild_annotation())
        strPrompt = (
            f"{label} [{defaultValue}]: " if defaultValue is not None else f"{label}: "
        )

        while True:
            strInput = input(strPrompt).strip()
            inputValue: str | int = (
                defaultValue if not strInput and defaultValue is not None else strInput
            )
            if fieldInfo.annotation is int:
                try:
                    inputValue = int(inputValue)
                except ValueError:
                    print("Enter a whole number.")
                    continue
            try:
                return valueAdapter.validate_python(inputValue, strict=True)
            except ValidationError as e:
                print(e.errors(include_input=False, include_url=False)[0]["msg"])

    def _prompt_password(label: str) -> str:
        while True:
            strPassword = read_password(f"{label}: ")
            if not strPassword.strip():
                print("Password must not be empty.")
                continue
            if any(
                ord(strCharacter) < 32 or ord(strCharacter) == 127
                for strCharacter in strPassword
            ):
                print("Password must not contain control characters.")
                continue
            return strPassword

    def _replace_config_value(content: str, fieldName: str, value: str | int) -> str:
        return re.sub(
            rf'(^[ \t]*"{fieldName}":[ \t]*)("(?:[^"\\]|\\.)*"|[0-9]+)',
            lambda matchObj: matchObj[1] + json.dumps(value, ensure_ascii=False),
            content,
            flags=re.MULTILINE,
        )

    def _write_secret_file(secretPath: Path, secretValue: str) -> None:
        intFileDescriptor = os.open(
            secretPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(intFileDescriptor, "w", encoding="utf-8") as secretFile:
            secretFile.write(secretValue)

    pathLocal = _PATH_CONSOLE / ".local"
    if pathLocal.exists():
        raise SystemExit(f"Local configuration already exists: {pathLocal}")

    pathTemplate = _PATH_CONSOLE / "Console.example.jsonc"
    strContent = pathTemplate.read_text(encoding="utf-8-sig")
    templateConfig = parse_config(strContent.encode("utf-8"), pathTemplate)
    dictDatabase = templateConfig.database.model_dump()
    dictSmtp = templateConfig.smtp.model_dump()

    print("Local development setup. Press Enter to use a shown default.")
    try:
        print("\nDatabase")
        for strFieldName, strLabel in (
            ("host", "Host"),
            ("port", "Port"),
            ("name", "Database name"),
            ("user", "Username"),
        ):
            dictDatabase[strFieldName] = _prompt_config_field(
                DatabaseConfig, strFieldName, strLabel, dictDatabase[strFieldName]
            )
        strDatabasePassword = _prompt_password("Database password")

        print("\nEmail")
        dictSmtp["host"] = _prompt_config_field(SmtpConfig, "host", "SMTP host")
        dictSmtp["security"] = _prompt_config_field(
            SmtpConfig, "security", "Security (ssl/starttls)", "ssl"
        )
        dictSmtp["port"] = _prompt_config_field(
            SmtpConfig, "port", "SMTP port", 465 if dictSmtp["security"] == "ssl" else 587
        )
        dictSmtp["user"] = _prompt_config_field(SmtpConfig, "user", "SMTP username")
        strSmtpPassword = _prompt_password("SMTP password")

        emailAdapter: TypeAdapter[str] = TypeAdapter(EmailAddress)
        try:
            strSenderDefault = emailAdapter.validate_python(dictSmtp["user"], strict=True)
        except ValidationError:
            strSenderDefault = None
        dictSmtp["fromEmail"] = _prompt_config_field(
            SmtpConfig, "fromEmail", "Sender email", strSenderDefault
        )

        print("\nSupport")
        strSupportEmail = _prompt_config_field(
            ConsoleConfig, "supportEmail", "Support email"
        )
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nSetup cancelled.") from None
    except PasswordInputError as e:
        raise SystemExit(str(e)) from None

    # Update only the bundled template's connection fields, preserving its comments.
    for strSectionName, dictValue in (("database", dictDatabase), ("smtp", dictSmtp)):
        sectionMatch = re.search(
            rf'^  "{strSectionName}": \{{.*?^  \}}',
            strContent,
            flags=re.MULTILINE | re.DOTALL,
        )
        if sectionMatch is None:
            raise ValueError(f"Missing {strSectionName} section in {pathTemplate}.")
        strSection = sectionMatch[0]
        for strFieldName, fieldValue in dictValue.items():
            strSection = _replace_config_value(strSection, strFieldName, fieldValue)
        strContent = (
            strContent[: sectionMatch.start()]
            + strSection
            + strContent[sectionMatch.end() :]
        )
    strContent = _replace_config_value(strContent, "supportEmail", strSupportEmail)

    pathConfig = pathLocal / "Console.jsonc"
    config = parse_config(strContent.encode("utf-8"), pathConfig)
    dictExpectedConfig = templateConfig.model_dump()
    dictExpectedConfig.update(
        database=dictDatabase, smtp=dictSmtp, supportEmail=strSupportEmail
    )
    if config.model_dump() != dictExpectedConfig:
        raise ValueError(f"Could not apply development settings to {pathTemplate}.")

    pathLocal.mkdir(mode=0o700)
    pathSecrets = pathLocal / "secrets"
    pathSecrets.mkdir(mode=0o700)
    _write_secret_file(pathSecrets / "django-secret-key.txt", secrets.token_urlsafe(64))
    _write_secret_file(
        pathSecrets / "encryption-key.txt", Fernet.generate_key().decode("ascii")
    )
    _write_secret_file(pathSecrets / "database-password.txt", strDatabasePassword)
    _write_secret_file(pathSecrets / "smtp-password.txt", strSmtpPassword)
    pathConfig.write_text(strContent, encoding="utf-8")
    pathStorage = pathLocal / config.storageRoot
    pathStorage.mkdir(mode=0o700, parents=True, exist_ok=True)

    print(f"\nCreated local development configuration: {pathConfig}")
    print(f"Created storage directory: {pathStorage}")


if __name__ == "__main__":
    main()
