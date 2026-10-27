# FileName: model_settings.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

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
    "packages.apps.PackagesConfig",
    "schedules.apps.SchedulesConfig",
    "runs.apps.RunsConfig",
    "operations.apps.OperationsConfig",
    "notifications.apps.NotificationsConfig",
]
# Configure the custom user model before generating or applying initial migrations.
AUTH_USER_MODEL = "accounts.User"
