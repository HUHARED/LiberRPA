# FileName: recovery.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

STR_RESTORE_PENDING_FILE = "restore.pending"
STR_RESTORE_READY_FILE = "restore.ready"
_boolRestoreSetup = False


@contextmanager
def permit_restore_setup() -> Generator[None]:
    """Allow only this offline restore process to load models while its marker remains."""
    global _boolRestoreSetup
    if _boolRestoreSetup:
        raise RuntimeError("Restore setup is already active.")
    _boolRestoreSetup = True
    try:
        yield
    finally:
        _boolRestoreSetup = False


def require_completed_restore(configPath: Path) -> None:
    if not _boolRestoreSetup and (configPath.parent / STR_RESTORE_PENDING_FILE).exists():
        raise ImproperlyConfigured(
            "Restore is incomplete. Keep this instance stopped and inspect the offline restore result."
        )


def is_restored_service_pending_review(configPath: Path | None = None) -> bool:
    pathConfig = configPath if configPath is not None else Path(settings.CONSOLE_CONFIG_PATH)
    return (pathConfig.parent / STR_RESTORE_READY_FILE).exists()


def complete_restored_service_review() -> None:
    """Remove the final barrier only after the future-only schedule boundary commits."""
    (Path(settings.CONSOLE_CONFIG_PATH).parent / STR_RESTORE_READY_FILE).unlink(
        missing_ok=True
    )
