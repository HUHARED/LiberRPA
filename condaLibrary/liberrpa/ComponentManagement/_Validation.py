# FileName: _Validation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


def add_issue(issues: list[dict[str, object]], field: str, message: str) -> None:
    issues.append({"field": field, "message": message})
