# FileName: backup_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.db.models import TextChoices


class BackupStage(TextChoices):
    SNAPSHOT = "snapshot", "Preparing snapshot"
    DATABASE = "database", "Exporting database"
    FILES = "files", "Copying files"
    VERIFYING = "verifying", "Verifying backup"
    FINALIZING = "finalizing", "Completing backup"
