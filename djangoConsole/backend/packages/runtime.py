# FileName: runtime.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from pydantic import ValidationError as ContractValidationError

from assets.models import Asset
from organizations.permissions import require_organization_business_available
from organizations.validators import get_path_name_key, validate_path_segment

from .contracts import RunSettings, validate_custom_arguments
from .models import Package

if TYPE_CHECKING:
    from schedules.models import Schedule


# NOTE: Keep these mappings aligned with RunSettings and both models when adding a run setting.
def build_run_settings(source: "Package | Schedule") -> dict:
    """Build shared execution settings without Package-only API input permissions."""
    return {
        "retry_count": source.retry_count,
        "timeout_min": source.timeout_min,
        "builtin_log_level": source.builtin_log_level,
        "builtin_record_video": source.builtin_record_video,
        "builtin_stop_shortcut": source.builtin_stop_shortcut,
        "builtin_highlight_ui": source.builtin_highlight_ui,
        "custom_prj_args": source.custom_prj_args,
        "custom_arg_assets": source.custom_arg_assets,
        "run_conflict_policy": source.run_conflict_policy,
        "priority": source.priority,
        "run_email": source.run_email,
    }


def apply_run_settings(target: "Package | Schedule", values: dict) -> None:
    """Assign already validated settings; the caller owns the database write."""
    target.retry_count = values["retry_count"]
    target.timeout_min = values["timeout_min"]
    target.builtin_log_level = values["builtin_log_level"]
    target.builtin_record_video = values["builtin_record_video"]
    target.builtin_stop_shortcut = values["builtin_stop_shortcut"]
    target.builtin_highlight_ui = values["builtin_highlight_ui"]
    target.custom_prj_args = values["custom_prj_args"]
    target.custom_arg_assets = values["custom_arg_assets"]
    target.run_conflict_policy = values["run_conflict_policy"]
    target.priority = values["priority"]
    target.run_email = values["run_email"]


def validate_run_settings(
    package: Package, settings: RunSettings, *, resolveAssets: bool = False
) -> dict:
    """Validate static configuration and optionally resolve the same checked assets for admission."""
    if [
        listArgument[0] for listArgument in settings.custom_prj_args
    ] != package.argument_names:
        raise ValidationError(
            "Custom argument names and positions must match the Package."
        )
    dictSettings = settings.model_dump(mode="json")
    if (
        len(json.dumps(dictSettings, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        > 2 * 1024 * 1024
    ):
        raise ValidationError("Run settings exceed the 2 MiB limit.")
    for binding in settings.custom_arg_assets:
        if binding is not None:
            validate_path_segment(binding.name)
    dictAsset = {
        asset.name_key: asset
        for asset in Asset.objects.filter(
            department_id=package.department_id,
            name_key__in={
                get_path_name_key(binding.name)
                for binding in settings.custom_arg_assets
                if binding is not None
            },
        )
    }
    for intIndex, binding in enumerate(settings.custom_arg_assets):
        if binding is None:
            continue
        asset = dictAsset.get(get_path_name_key(binding.name))
        if asset is None or asset.asset_type != binding.asset_type:
            raise ValidationError(
                f"Custom argument {intIndex + 1}: the same-department asset '{binding.name}' is missing or has a different type."
            )
        if resolveAssets:
            dictSettings["custom_prj_args"][intIndex][1] = json.loads(asset.value_json)
    if resolveAssets:
        if any(settings.custom_arg_assets):
            try:
                validate_custom_arguments(dictSettings["custom_prj_args"])
            except ValueError as e:
                raise ValidationError(str(e)) from None
        dictSettings["custom_arg_assets"] = []
    from notifications.run_email import validate_run_email

    validate_run_email(
        package.department.organization_id,
        dictSettings["run_email"],
        dictSettings["custom_prj_args"],
    )
    return dictSettings


def get_run_snapshot(
    package: Package,
    settingsOverride: dict | None = None,
    departmentId: uuid.UUID | None = None,
) -> dict:
    """Resolve same-department ordinary assets at admission, independently of the Executor account."""
    if departmentId is not None and departmentId != package.department_id:
        raise ValidationError("The Package and task must belong to the same department.")
    if package.department.deleted_at is not None:
        raise ValidationError("The Package department is unavailable.")
    require_organization_business_available(package.department.organization)
    try:
        runSettings = RunSettings.model_validate(
            settingsOverride
            if settingsOverride is not None
            else build_run_settings(package)
        )
    except ContractValidationError:
        raise ValidationError("The run settings are invalid.") from None
    dictSnapshot = validate_run_settings(package, runSettings, resolveAssets=True)
    dictSnapshot.update({
        "package_id": str(package.pk),
        "department_id": str(package.department_id),
        "project_name": package.project_name,
        "project_version": package.version,
        "version": package.version,
        "sha256": package.sha256,
        "requires_liberrpa": package.requires_liberrpa,
        "python_environment_name": package.python_environment_name,
    })
    return dictSnapshot
