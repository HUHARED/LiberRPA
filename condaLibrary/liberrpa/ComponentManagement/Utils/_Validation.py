# FileName: _Validation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError


def add_issue(issueList: list[dict[str, object]], field: str, message: str) -> None:
    issueList.append({"field": field, "message": message})


def raise_config_issues(issueList: list[dict[str, object]]) -> None:
    if not issueList:
        return

    raise ComponentManagementError(
        code="snippet_config_invalid",
        message="Invalid Component Snippet configuration.",
        details={"issues": issueList},
    )


def validate_json_object_fields(
    value: dict[object, object],
    allowedKeys: set[str],
    field: str,
    issueList: list[dict[str, object]],
) -> None:
    listUnknownKey: list[str] = []

    for key in value:
        if not isinstance(key, str):
            listUnknownKey.append(repr(key))
        elif key not in allowedKeys:
            listUnknownKey.append(key)

    listUnknownKey.sort()

    if listUnknownKey:
        add_issue(issueList, field, f"Unknown fields: {listUnknownKey}.")


def raise_rebuild_required(message: str, details: dict[str, object] | None = None) -> None:
    raise ComponentManagementError(
        code="repository_rebuild_required",
        message=message,
        details=details,
    )
