# FileName: settings.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .config import load_config, read_secret_file

_PATH_CONSOLE = Path(__file__).resolve().parents[2]
_PATH_CONFIG = Path(
    os.environ.get("LIBERRPA_CONSOLE_CONFIG", _PATH_CONSOLE / ".local/Console.jsonc")
).resolve()
_CONFIG = load_config(_PATH_CONFIG)

SECRET_KEY = read_secret_file(_PATH_CONFIG.parent / _CONFIG.secretKeyFile)
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "The Django secret key must contain at least 50 characters."
    )

DEBUG = _CONFIG.debug
ALLOWED_HOSTS = _CONFIG.allowedHosts
ROOT_URLCONF = "console_project.urls"
ASGI_APPLICATION = "console_project.asgi.application"

# Define the Console account before creating any database tables.
INSTALLED_APPS = ["accounts.apps.AccountsConfig"]
AUTH_USER_MODEL = "accounts.User"
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _CONFIG.database.name,
        "USER": _CONFIG.database.user,
        "PASSWORD": read_secret_file(_PATH_CONFIG.parent / _CONFIG.database.passwordFile),
        "HOST": _CONFIG.database.host,
        "PORT": _CONFIG.database.port,
        # ASGI requests should not keep Django's persistent database connections open.
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 3},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
