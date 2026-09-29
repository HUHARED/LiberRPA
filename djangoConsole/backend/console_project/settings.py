# FileName: settings.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
from email.headerregistry import Address
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .config import read_config, read_secret_file, read_secret_cipher
from .logging import build_logging_config

_PATH_CONSOLE = Path(__file__).resolve().parents[2]
_PATH_CONFIG = Path(
    os.environ.get("LIBERRPA_CONSOLE_CONFIG", _PATH_CONSOLE / ".local/Console.jsonc")
).resolve()
_CONSOLE_CONFIG = read_config(_PATH_CONFIG)

SECRET_KEY = read_secret_file(_PATH_CONFIG.parent / _CONSOLE_CONFIG.secretKeyFile)
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "The Django secret key must contain at least 50 characters."
    )

DEBUG = _CONSOLE_CONFIG.debug
ALLOWED_HOSTS = _CONSOLE_CONFIG.allowedHosts
ROOT_URLCONF = "console_project.urls"
ASGI_APPLICATION = "console_project.asgi.application"
CONSOLE_LIMITS = _CONSOLE_CONFIG.limits
CONSOLE_STORAGE_ROOT = (_PATH_CONFIG.parent / _CONSOLE_CONFIG.storageRoot).resolve()
CONSOLE_SECRET_CIPHER = read_secret_cipher(
    _PATH_CONFIG.parent, _CONSOLE_CONFIG.encryptionKeyFiles
)
CONSOLE_LOG_REQUESTS = _CONSOLE_CONFIG.logging.requests
LOGGING = build_logging_config(_CONSOLE_CONFIG.logging.level)
CONSOLE_URL = str(_CONSOLE_CONFIG.consoleUrl).rstrip("/")
CONSOLE_SUPPORT_EMAIL = _CONSOLE_CONFIG.supportEmail

DEFAULT_FROM_EMAIL = str(
    Address(
        display_name=_CONSOLE_CONFIG.smtp.fromName,
        addr_spec=_CONSOLE_CONFIG.smtp.fromEmail,
    )
)
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": _CONSOLE_CONFIG.smtp.host,
            "port": _CONSOLE_CONFIG.smtp.port,
            "username": _CONSOLE_CONFIG.smtp.user,
            "password": read_secret_file(
                _PATH_CONFIG.parent / _CONSOLE_CONFIG.smtp.passwordFile
            ),
            "use_ssl": _CONSOLE_CONFIG.smtp.security == "ssl",
            "use_tls": _CONSOLE_CONFIG.smtp.security == "starttls",
            "timeout": _CONSOLE_CONFIG.smtp.timeoutSeconds,
        },
    }
}

# Define the Console account before creating any database tables.
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "accounts.apps.AccountsConfig",
    "organizations.apps.OrganizationsConfig",
    "executors.apps.ExecutorsConfig",
    "assets.apps.AssetsConfig",
    "data_queues.apps.DataQueuesConfig",
    "file_storage.apps.FileStorageConfig",
    "shared_files.apps.SharedFilesConfig",
    "operations.apps.OperationsConfig",
    "notifications.apps.NotificationsConfig",
]
AUTH_USER_MODEL = "accounts.User"
# Authenticate identity with Django; Console business permissions remain in organizations.permissions.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Web sessions have an absolute expiry chosen at login, never a sliding expiry.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Cookie transport follows the configured browser-facing URL, including local HTTP development.
SESSION_COOKIE_SECURE = CONSOLE_URL.startswith("https://")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_FAILURE_VIEW = "console_project.http.csrf_failure"
# New-password entry points also enforce length in validate_new_password().
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ["email", "username"]},
    },
]
MIDDLEWARE = [
    "console_project.middleware.request_logging",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _CONSOLE_CONFIG.database.name,
        "USER": _CONSOLE_CONFIG.database.user,
        "PASSWORD": read_secret_file(
            _PATH_CONFIG.parent / _CONSOLE_CONFIG.database.passwordFile
        ),
        "HOST": _CONSOLE_CONFIG.database.host,
        "PORT": _CONSOLE_CONFIG.database.port,
        # ASGI requests should not keep Django's persistent database connections open.
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 3},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
