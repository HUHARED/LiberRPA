# FileName: manage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import os
import sys

from django.core.management import execute_from_command_line
from django.db import DatabaseError

_LOGGER = logging.getLogger("console.management")


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "console_project.settings")
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    try:
        main()
    except DatabaseError:
        _LOGGER.exception("Management command stopped after a database error.")
        raise SystemExit(1) from None
