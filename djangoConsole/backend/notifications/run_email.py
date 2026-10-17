# FileName: run_email.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import re
import uuid
from typing import TYPE_CHECKING
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage

from console_project.contracts import JsonValue
from packages.contracts import RunEmailSettings

from .models import RunEmailEvent
from .recipients import get_eligible_recipients

if TYPE_CHECKING:
    from runs.models import Run

_RE_FIELD = re.compile(
    r'{{((?:Input_CustomArgs|Output_CustomArgs)\["(?:[^"\\]|\\.)*"\]|[A-Za-z_][A-Za-z0-9_]*)}}'
)
_RE_SUBJECT_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_INT_MAX_SUBJECT_LENGTH = 256
_INT_MAX_BODY_TEMPLATE_BYTES = 16 * 1024
_INT_MAX_BODY_BYTES = 64 * 1024
_INT_MAX_CONTEXT_KEYS = 64
_INT_MAX_VALUE_BYTES = 16 * 1024
_INT_MAX_CONTEXT_BYTES = 64 * 1024
_INT_MAX_VALUE_DEPTH = 8
_DICT_EVENT_KEY = {
    RunEmailEvent.START: "on_start",
    RunEmailEvent.COMPLETED: "on_completed",
    RunEmailEvent.ERROR: "on_error",
}
_SET_COMMON_FIELD = frozenset({
    "organization_name",
    "department_name",
    "project_name",
    "project_version",
    "trigger_source",
    "schedule_name",
    "scheduled_at",
    "executor_name",
    "computer_name",
    "account_name",
    "python_environment_name",
    "started_at",
    "job_id",
    "run_id",
    "details_url",
})
_SET_END_FIELD = frozenset({"ended_at", "elapsed_seconds"})
_SET_ERROR_FIELD = frozenset({"error_type", "error_message"})
_STR_COMMON_BODY = """Department: {{department_name}}
Project: {{project_name}}
Version: {{project_version}}

Trigger source: {{trigger_source}}
Schedule: {{schedule_name}}
Scheduled at: {{scheduled_at}}

Executor: {{executor_name}}
Computer: {{computer_name}}
Account: {{account_name}}
Python environment: {{python_environment_name}}

Started at: {{started_at}}"""
_STR_LINK_BODY = """Run details:
{{details_url}}

Opening this link requires a Console account with access to the run."""
DEFAULT_TEMPLATES = {
    "on_start": {
        "subject": "{{project_name}} — Started",
        "body": "A run has started.\n\n" + _STR_COMMON_BODY + "\n\n" + _STR_LINK_BODY,
    },
    "on_completed": {
        "subject": "{{project_name}} — Completed",
        "body": "The run completed successfully.\n\n"
        + _STR_COMMON_BODY
        + "\nEnded at: {{ended_at}}\nDuration (seconds): {{elapsed_seconds}}\n\n"
        + _STR_LINK_BODY,
    },
    "on_error": {
        "subject": "{{project_name}} — Error",
        "body": "The run ended with an error.\n\n"
        + _STR_COMMON_BODY
        + "\nEnded at: {{ended_at}}\nDuration (seconds): {{elapsed_seconds}}\n\nError type: {{error_type}}\nError message:\n{{error_message}}\n\n"
        + _STR_LINK_BODY,
    },
}


def get_template_metadata() -> dict:
    return {
        "defaults": DEFAULT_TEMPLATES,
        "system_fields": [
            {
                "name": strName,
                "events": [
                    str(event)
                    for event in RunEmailEvent
                    if strName in _SET_COMMON_FIELD
                    or event != RunEmailEvent.START
                    and strName in _SET_END_FIELD
                    or event == RunEmailEvent.ERROR
                    and strName in _SET_ERROR_FIELD
                ],
            }
            for strName in sorted(_SET_COMMON_FIELD | _SET_END_FIELD | _SET_ERROR_FIELD)
        ],
    }


def validate_run_email(
    organizationId: uuid.UUID, config: RunEmailSettings, customArgs: list[list[JsonValue]]
) -> None:
    listRecipientId = config.recipient_ids
    dictFieldError: dict[str, list[str]] = {}
    strRecipientField = "settings.run_email.recipient_ids"
    if len(set(listRecipientId)) != len(listRecipientId):
        dictFieldError[strRecipientField] = [
            "Select at most five distinct eligible Run email recipients."
        ]
    elif listRecipientId and get_eligible_recipients(organizationId).filter(
        pk__in=listRecipientId
    ).count() != len(listRecipientId):
        dictFieldError[strRecipientField] = [
            "Select current member emails or independently verified addresses in this organization."
        ]
    setInputField = {
        f"Input_CustomArgs[{json.dumps(str(entry[0]), ensure_ascii=False)}]"
        for entry in customArgs
    }
    setOutputField = {
        f"Output_CustomArgs[{json.dumps(str(entry[0]), ensure_ascii=False)}]"
        for entry in customArgs
    }
    for event, strKey, template in (
        (RunEmailEvent.START, "on_start", config.on_start),
        (RunEmailEvent.COMPLETED, "on_completed", config.on_completed),
        (RunEmailEvent.ERROR, "on_error", config.on_error),
    ):
        strPrefix = f"settings.run_email.{strKey}"
        if (
            _RE_SUBJECT_CONTROL.search(template.subject) is not None
            or len(template.subject) > _INT_MAX_SUBJECT_LENGTH
        ):
            dictFieldError[f"{strPrefix}.subject"] = [
                "Enter one line of up to 256 characters without control characters."
            ]
        if (
            len(template.body.encode("utf-8")) > _INT_MAX_BODY_TEMPLATE_BYTES
            or "\x00" in template.body
        ):
            dictFieldError[f"{strPrefix}.body"] = [
                "Enter a body of at most 16 KiB without null characters."
            ]
        if (
            len(set(_RE_FIELD.findall(template.subject + template.body)))
            > _INT_MAX_CONTEXT_KEYS
        ):
            dictFieldError[f"{strPrefix}.body"] = [
                "A Run email template can reference at most 64 different fields."
            ]
        setAllowed = _SET_COMMON_FIELD | setInputField
        if event != RunEmailEvent.START:
            setAllowed |= _SET_END_FIELD | setOutputField
        if event == RunEmailEvent.ERROR:
            setAllowed |= _SET_ERROR_FIELD
        for strField, strTemplate in (
            ("subject", template.subject),
            ("body", template.body),
        ):
            strRemainder = _RE_FIELD.sub("", strTemplate)
            if (
                any(
                    strName not in setAllowed
                    for strName in _RE_FIELD.findall(strTemplate)
                )
                or "{{" in strRemainder
                or "}}" in strRemainder
            ):
                dictFieldError.setdefault(f"{strPrefix}.{strField}", []).append(
                    "This template references an unknown or unavailable field."
                )
    if dictFieldError:
        raise ValidationError(dictFieldError)


def _format_time(value: datetime | None, zone: ZoneInfo) -> str:
    if value is None:
        return "Not available"
    strValue = value.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S %z")
    return strValue[:-2] + ":" + strValue[-2:]


def _has_valid_value_depth(value: object, depth: int = 0) -> bool:
    if depth > _INT_MAX_VALUE_DEPTH:
        return False
    if isinstance(value, dict):
        return all(_has_valid_value_depth(entry, depth + 1) for entry in value.values())
    if isinstance(value, list):
        return all(_has_valid_value_depth(entry, depth + 1) for entry in value)
    return True


def _render_value(value: object) -> str:
    if not _has_valid_value_depth(value):
        return "Not available (value exceeds email depth limit)"
    strValue = json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    return (
        strValue
        if len(strValue.encode("utf-8")) <= _INT_MAX_VALUE_BYTES
        else "Not available (value exceeds email limit)"
    )


def build_run_email(run: "Run", *, event: str, recipient: str) -> EmailMessage:
    job = run.job
    jobRequest = job.request
    organization = jobRequest.organization
    zone = ZoneInfo(organization.default_time_zone)
    assignment = run.assignment
    strEventKey = _DICT_EVENT_KEY[RunEmailEvent(event)]
    dictTemplate = job.run_snapshot["run_email"][strEventKey]
    dictDefault = DEFAULT_TEMPLATES[strEventKey]
    strSubject = dictTemplate["subject"] or dictDefault["subject"]
    strBody = dictTemplate["body"] or dictDefault["body"]
    dictField = {
        "organization_name": organization.name,
        "department_name": job.department.name,
        "project_name": job.project_name,
        "project_version": job.project_version,
        "trigger_source": "API"
        if jobRequest.source == "api"
        else jobRequest.source.capitalize(),
        "schedule_name": jobRequest.schedule_name or "Not applicable",
        "scheduled_at": _format_time(jobRequest.scheduled_at, zone)
        if jobRequest.scheduled_at
        else "Not applicable",
        "executor_name": assignment.executor_name,
        "computer_name": assignment.computer_name,
        "account_name": assignment.actor_name,
        "python_environment_name": job.run_snapshot["python_environment_name"],
        "started_at": _format_time(run.started_at, zone),
        "ended_at": _format_time(run.ended_at, zone),
        "elapsed_seconds": str((run.ended_at - run.started_at).total_seconds())
        if run.ended_at
        else "Not available",
        "job_id": str(job.pk),
        "run_id": str(run.pk),
        "details_url": f"{settings.CONSOLE_URL}/runs/{run.pk}",
        "error_type": (run.error_summary or {}).get("type", "Not available"),
        "error_message": (run.error_summary or {}).get("message", "Not available"),
    }
    dictInput = dict(job.run_snapshot["custom_prj_args"])
    dictOutput = dict(run.outputs or [])
    for strField in dict.fromkeys(_RE_FIELD.findall(strSubject + strBody)):
        for strPrefix, dictValue in (
            ("Input_CustomArgs", dictInput),
            ("Output_CustomArgs", dictOutput),
        ):
            if strField.startswith(strPrefix + "["):
                strName = json.loads(strField[len(strPrefix) + 1 : -1])
                dictField[strField] = (
                    _render_value(dictValue[strName])
                    if strName in dictValue
                    else "Not available"
                )
    intContextBytes = 0
    for strField in dict.fromkeys(_RE_FIELD.findall(strSubject + strBody)):
        strValue = str(dictField.get(strField, "Not available"))
        intValueBytes = len(strValue.encode("utf-8"))
        if intContextBytes + intValueBytes > _INT_MAX_CONTEXT_BYTES:
            dictField[strField] = "Not available (email context limit)"
        else:
            intContextBytes += intValueBytes
    # Replacement values remain literal; they are never scanned for another template pass.
    strRenderedSubject = _RE_SUBJECT_CONTROL.sub(
        " ",
        _RE_FIELD.sub(
            lambda match: str(dictField.get(match[1], "Not available")), strSubject
        ),
    )[:_INT_MAX_SUBJECT_LENGTH]
    strRenderedBody = _RE_FIELD.sub(
        lambda match: str(dictField.get(match[1], "Not available")), strBody
    )
    bodyBytes = strRenderedBody.encode("utf-8")
    if len(bodyBytes) > _INT_MAX_BODY_BYTES:
        strSuffix = "\n[Email body truncated at 64 KiB.]"
        strRenderedBody = (
            bodyBytes[: _INT_MAX_BODY_BYTES - len(strSuffix)].decode(
                "utf-8", errors="ignore"
            )
            + strSuffix
        )
    return EmailMessage(
        subject=strRenderedSubject,
        body=strRenderedBody,
        to=[recipient],
        reply_to=[settings.CONSOLE_SUPPORT_EMAIL],
    )
