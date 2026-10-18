# FileName: runtime.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from pydantic import ValidationError as ContractValidationError

from assets.models import Asset
from organizations.validators import get_path_name_key, validate_path_segment

from console_project.contracts import JsonValue
from console_project.http import get_contract_error_fields

from .contracts import RunSettings, validate_custom_arguments
from .models import Package

if TYPE_CHECKING:
    from schedules.models import Schedule


# NOTE: Keep these mappings aligned with RunSettings and both models when adding a run setting.
def parse_run_settings(
    source: "Package | Schedule", *, overrides: dict[str, JsonValue] | None = None
) -> RunSettings:
    """Parse saved settings and request overrides once when they enter this workflow."""
    dictSettings: dict[str, object] = {
        "max_retry_count": source.max_retry_count,
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
    if overrides:
        dictSettings.update(overrides)
    try:
        return RunSettings.model_validate(dictSettings)
    except ContractValidationError as e:
        raise ValidationError(get_contract_error_fields(e, prefix="settings")) from None


def apply_run_settings(target: "Package | Schedule", values: RunSettings) -> None:
    """Assign validated settings; convert structured values to JSON only for database storage."""
    target.max_retry_count = values.max_retry_count
    target.timeout_min = values.timeout_min
    target.builtin_log_level = values.builtin_log_level
    target.builtin_record_video = values.builtin_record_video
    target.builtin_stop_shortcut = values.builtin_stop_shortcut
    target.builtin_highlight_ui = values.builtin_highlight_ui
    target.custom_prj_args = values.custom_prj_args
    target.custom_arg_assets = [
        binding.model_dump(mode="json") if binding is not None else None
        for binding in values.custom_arg_assets
    ]
    target.run_conflict_policy = values.run_conflict_policy
    target.priority = values.priority
    target.run_email = values.run_email.model_dump(mode="json")


def validate_run_settings(
    package: Package,
    settings: RunSettings,
    *,
    resolveAssets: bool = False,
    emailOutputKeys: dict[str, list[str]] | None = None,
) -> RunSettings:
    """Check current business facts without parsing the settings model again."""
    if [entry[0] for entry in settings.custom_prj_args] != package.argument_names:
        raise ValidationError({
            "settings.custom_prj_args": (
                "Custom argument names and positions must match the Package."
            )
        })
    if len(settings.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
        raise ValidationError({"settings": "Run settings exceed the 2 MiB limit."})
    for intIndex, binding in enumerate(settings.custom_arg_assets):
        if binding is not None:
            try:
                validate_path_segment(binding.name)
            except ValidationError as e:
                raise ValidationError({
                    f"settings.custom_arg_assets.{intIndex}.name": e.messages
                }) from None
    setAssetKey = {
        get_path_name_key(binding.name)
        for binding in settings.custom_arg_assets
        if binding is not None
    }
    dictAsset = (
        {
            asset.name_key: asset
            for asset in Asset.objects.filter(
                department_id=package.department_id, name_key__in=setAssetKey
            )
        }
        if setAssetKey
        else {}
    )
    # Resolving a run must not replace the saved defaults or another attempt's inputs.
    listArgument = (
        [entry.copy() for entry in settings.custom_prj_args]
        if resolveAssets
        else settings.custom_prj_args
    )
    dictBindingError: dict[str, list[str]] = {}
    for intIndex, binding in enumerate(settings.custom_arg_assets):
        if binding is None:
            continue
        asset = dictAsset.get(get_path_name_key(binding.name))
        if asset is None or asset.asset_type != binding.asset_type:
            dictBindingError[f"settings.custom_arg_assets.{intIndex}.name"] = [
                f"The same-department asset '{binding.name}' is missing or has a different type."
            ]
        elif resolveAssets:
            listArgument[intIndex][1] = json.loads(asset.value_json)
    if dictBindingError:
        raise ValidationError(dictBindingError)
    if resolveAssets and setAssetKey:
        try:
            validate_custom_arguments(listArgument)
        except ValueError as e:
            raise ValidationError({"settings.custom_prj_args": str(e)}) from None
    from notifications.run_email import validate_run_email

    dictEmailOutputKey = validate_run_email(
        package.department.organization_id, settings.run_email, listArgument
    )
    if emailOutputKeys is not None:
        emailOutputKeys.update(dictEmailOutputKey)
    return (
        settings.model_copy(
            update={
                "custom_prj_args": listArgument,
                "custom_arg_assets": [],
            }
        )
        if resolveAssets
        else settings
    )


def get_run_snapshot(package: Package, settings: RunSettings) -> dict[str, JsonValue]:
    """Read current asset values, then convert the accepted run settings to JSON for storage."""
    dictEmailOutputKey: dict[str, list[str]] = {}
    runSettings = validate_run_settings(
        package, settings, resolveAssets=True, emailOutputKeys=dictEmailOutputKey
    )
    dictSnapshot: dict[str, JsonValue] = runSettings.model_dump(mode="json")
    dictSnapshot.update({
        "email_output_keys": {
            strEvent: list(listKey) for strEvent, listKey in dictEmailOutputKey.items()
        },
        "package_id": str(package.pk),
        "department_id": str(package.department_id),
        "project_name": package.project_name,
        "project_version": package.project_version,
        "sha256": package.sha256,
        "requires_liberrpa": package.requires_liberrpa,
        "python_environment_name": package.python_environment_name,
    })
    return dictSnapshot
