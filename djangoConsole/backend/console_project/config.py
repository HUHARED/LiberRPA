# FileName: config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
from typing import Annotated

import json5
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

type NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _BaseConfig(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class DatabaseConfig(_BaseConfig):
    host: NonEmptyText
    port: int = Field(ge=1, le=65535)
    name: NonEmptyText
    user: NonEmptyText
    passwordFile: NonEmptyText


class LimitsConfig(_BaseConfig):
    maxDepartmentsPerOrganization: int = Field(default=20, ge=0)
    maxDepartmentDepth: int = Field(default=5, ge=1)


class ConsoleConfig(_BaseConfig):
    debug: bool = False
    allowedHosts: list[NonEmptyText] = Field(min_length=1)
    secretKeyFile: NonEmptyText
    database: DatabaseConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)


def load_config(pathConfig: Path) -> ConsoleConfig:
    try:
        strConfig = pathConfig.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as e:
        raise ImproperlyConfigured(
            f"Cannot read Console configuration: {pathConfig}"
        ) from e

    try:
        dictConfig = json5.loads(strConfig, allow_duplicate_keys=False)
    except ValueError:
        raise ImproperlyConfigured(
            f"Invalid JSONC or duplicate configuration keys: {pathConfig}"
        ) from None

    try:
        return ConsoleConfig.model_validate(dictConfig)
    except ValidationError as e:
        raise ImproperlyConfigured(f"Invalid Console configuration: {e}") from None


def read_secret_file(pathSecret: Path) -> str:
    try:
        # Remove text-file line endings without changing spaces in a password.
        secretValue = pathSecret.read_text(encoding="utf-8-sig").rstrip("\r\n")
    except (OSError, UnicodeError) as e:
        raise ImproperlyConfigured(f"Cannot read secret file: {pathSecret}") from e

    if not secretValue.strip():
        raise ImproperlyConfigured(f"Secret file is empty: {pathSecret}")
    return secretValue
