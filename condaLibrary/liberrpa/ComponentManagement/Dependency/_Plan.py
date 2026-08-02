# FileName: _Plan.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import serialize_json
from liberrpa.ComponentManagement.Common._Version import normalize_specifier
from liberrpa.ComponentManagement.Common._Validation import validate_exact_keys
from liberrpa.ComponentManagement.Types._Manifest import (
    Info_ProjectManifest_Flow,
    Info_ProjectManifest_Component,
    Info_ProjectManifest,
)
from liberrpa.ComponentManagement.Types._Repository import DictRepository_Index
from liberrpa.ComponentManagement.Types._Components import (
    DictComponentsLock_Component,
    DictComponentsLock_File,
)
from liberrpa.ComponentManagement.Types._Dependency import (
    Info_ProjectDependency_Operation_Add,
    Info_ProjectDependency_Operation_Update,
    Info_ProjectDependency_Operation_ChangeRequirement,
    Info_ProjectDependency_Operation_Remove,
    Info_ProjectDependency_Operation,
    DictProjectDependency_DirectChange,
    Str_ProjectDependency_ResolvedChange,
    DictProjectDependency_ResolvedChange,
    Info_ProjectDependency_Plan,
)
from liberrpa.ComponentManagement.Dependency._ComponentsLock import validate_components_lock
from liberrpa.ComponentManagement.Dependency._Resolver import resolve_project_dependencies
from liberrpa.ComponentManagement.Manifest._Manifest import build_project_manifest_dict
from liberrpa.ComponentManagement.Repository._Index import normalize_component_id

from dataclasses import replace
from hashlib import sha256
from packaging.version import Version
from typing import NoReturn, assert_never


def _raise_invalid_plan_input(
    message: str,
    details: dict[str, object] | None = None,
) -> NoReturn:
    raise ComponentManagementError(
        code="dependency_plan_invalid_input",
        message=message,
        details=details,
    )


def _normalize_requirement(value: object, field: str) -> str:
    if not isinstance(value, str):
        _raise_invalid_plan_input(
            f"{field} must be a string.",
            {"field": field},
        )

    if value != value.strip():
        _raise_invalid_plan_input(
            f"{field} cannot start or end with whitespace.",
            {"field": field},
        )

    try:
        return normalize_specifier(value)
    except ValueError as e:
        _raise_invalid_plan_input(
            f"{field} is invalid.",
            {
                "field": field,
                "reason": str(e),
            },
        )


def _normalize_operation_component_id(value: object, field: str) -> str:
    try:
        return normalize_component_id(value, field)
    except ValueError as e:
        _raise_invalid_plan_input(
            f"{field} is invalid.",
            {
                "field": field,
                "reason": str(e),
            },
        )


def _normalize_dependency_operation(
    operationObj: Info_ProjectDependency_Operation,
) -> Info_ProjectDependency_Operation:
    if isinstance(operationObj, Info_ProjectDependency_Operation_Add):
        return Info_ProjectDependency_Operation_Add(
            componentId=_normalize_operation_component_id(
                operationObj.componentId,
                "operation.componentId",
            ),
            requirement=_normalize_requirement(
                operationObj.requirement,
                "operation.requirement",
            ),
        )

    if isinstance(operationObj, Info_ProjectDependency_Operation_ChangeRequirement):
        return Info_ProjectDependency_Operation_ChangeRequirement(
            componentId=_normalize_operation_component_id(
                operationObj.componentId,
                "operation.componentId",
            ),
            requirement=_normalize_requirement(
                operationObj.requirement,
                "operation.requirement",
            ),
        )

    if isinstance(operationObj, Info_ProjectDependency_Operation_Remove):
        return Info_ProjectDependency_Operation_Remove(
            componentId=_normalize_operation_component_id(
                operationObj.componentId,
                "operation.componentId",
            ),
        )

    if isinstance(operationObj, Info_ProjectDependency_Operation_Update):
        if not operationObj.componentIds:
            _raise_invalid_plan_input("Update requires at least one Component ID.")

        listNormalizedComponentId = [
            _normalize_operation_component_id(
                componentId,
                f"operation.componentIds.{intIndex}",
            )
            for intIndex, componentId in enumerate(operationObj.componentIds)
        ]
        if len(set(listNormalizedComponentId)) != len(listNormalizedComponentId):
            _raise_invalid_plan_input(
                "Update contains the same Component ID more than once.",
            )

        return Info_ProjectDependency_Operation_Update(
            componentIds=tuple(sorted(listNormalizedComponentId)),
        )

    _raise_invalid_plan_input(
        "Unsupported Project dependency operation.",
        {"operationType": type(operationObj).__name__},
    )


def parse_project_dependency_operation(
    value: object,
) -> Info_ProjectDependency_Operation:
    """Parse and normalize a dependency operation from protocol-compatible JSON data."""
    if not isinstance(value, dict):
        _raise_invalid_plan_input("dependencyOperation must be an object.")

    operationValue = value.get("operation")

    try:
        if operationValue == "addComponentDependency":
            validate_exact_keys(
                value,
                {"operation", "componentId", "requirement"},
                "dependencyOperation",
            )
            componentId = value.get("componentId")
            requirement = value.get("requirement")
            if not isinstance(componentId, str) or not isinstance(requirement, str):
                _raise_invalid_plan_input(
                    "Add Component Dependency requires string componentId and requirement fields."
                )
            operationObj: Info_ProjectDependency_Operation = Info_ProjectDependency_Operation_Add(
                componentId=componentId,
                requirement=requirement,
            )

        elif operationValue == "updateComponents":
            validate_exact_keys(
                value,
                {"operation", "componentIds"},
                "dependencyOperation",
            )
            componentIdValue = value.get("componentIds")
            if not isinstance(componentIdValue, list):
                _raise_invalid_plan_input("Update Components requires componentIds to be an array of strings.")

            listComponentId: list[str] = []
            for componentId in componentIdValue:
                if not isinstance(componentId, str):
                    _raise_invalid_plan_input("Update Components requires componentIds to be an array of strings.")
                listComponentId.append(componentId)

            operationObj = Info_ProjectDependency_Operation_Update(
                componentIds=tuple(listComponentId),
            )

        elif operationValue == "changeComponentRequirement":
            validate_exact_keys(
                value,
                {"operation", "componentId", "requirement"},
                "dependencyOperation",
            )
            componentId = value.get("componentId")
            requirement = value.get("requirement")
            if not isinstance(componentId, str) or not isinstance(requirement, str):
                _raise_invalid_plan_input(
                    "Change Component Requirement requires string componentId and requirement fields."
                )
            operationObj = Info_ProjectDependency_Operation_ChangeRequirement(
                componentId=componentId,
                requirement=requirement,
            )

        elif operationValue == "removeComponentDependency":
            validate_exact_keys(
                value,
                {"operation", "componentId"},
                "dependencyOperation",
            )
            componentId = value.get("componentId")
            if not isinstance(componentId, str):
                _raise_invalid_plan_input("Remove Component Dependency requires componentId to be a string.")
            operationObj = Info_ProjectDependency_Operation_Remove(
                componentId=componentId,
            )

        else:
            _raise_invalid_plan_input(
                "dependencyOperation contains an unsupported operation.",
                {"operation": operationValue},
            )
    except ValueError as e:
        _raise_invalid_plan_input(
            "dependencyOperation contains missing or unknown fields.",
            {"reason": str(e)},
        )

    return _normalize_dependency_operation(operationObj)


def _normalize_source_components_lock(
    manifestObj: Info_ProjectManifest,
    existingLock: DictComponentsLock_File | None,
) -> DictComponentsLock_File | None:
    if existingLock is None:
        return None

    try:
        dictValidatedLock = validate_components_lock(existingLock)
    except ValueError as e:
        _raise_invalid_plan_input(
            "existingLock is not a valid components.lock.json.",
            {"reason": str(e)},
        )

    dictRoot = dictValidatedLock["root"]
    if isinstance(manifestObj, Info_ProjectManifest_Flow):
        if dictRoot["manifestFile"] != "flow.json":
            _raise_invalid_plan_input(
                "existingLock belongs to a Component Project, not the current Flow Project.",
            )
        return dictValidatedLock

    if dictRoot["manifestFile"] != "component.json":
        _raise_invalid_plan_input(
            "existingLock belongs to a Flow Project, not the current Component Project.",
        )

    if dictRoot["componentId"] != manifestObj.id:
        _raise_invalid_plan_input(
            "existingLock belongs to a different root Component ID.",
            {
                "manifestComponentId": manifestObj.id,
                "lockComponentId": dictRoot["componentId"],
            },
        )

    if dictRoot["packageName"] != manifestObj.packageName:
        _raise_invalid_plan_input(
            "existingLock belongs to a different root Component packageName.",
            {
                "manifestPackageName": manifestObj.packageName,
                "lockPackageName": dictRoot["packageName"],
            },
        )

    return dictValidatedLock


def _replace_manifest_dependencies(
    manifestObj: Info_ProjectManifest,
    componentDependencyDict: dict[str, str],
) -> Info_ProjectManifest:
    return replace(
        manifestObj,
        componentDependencies=dict(sorted(componentDependencyDict.items())),
    )


def _build_target_manifest(
    sourceManifestObj: Info_ProjectManifest,
    operationObj: Info_ProjectDependency_Operation,
) -> Info_ProjectManifest:
    dictTargetDependency = dict(sourceManifestObj.componentDependencies)

    if isinstance(operationObj, Info_ProjectDependency_Operation_Add):
        if isinstance(sourceManifestObj, Info_ProjectManifest_Component) and operationObj.componentId == sourceManifestObj.id:
            _raise_invalid_plan_input("A Component cannot depend on itself.")

        strExistingRequirement = dictTargetDependency.get(operationObj.componentId)
        if strExistingRequirement is not None:
            _raise_invalid_plan_input(
                "The Component is already a direct Project dependency.",
                {
                    "componentId": operationObj.componentId,
                    "existingRequirement": strExistingRequirement,
                },
            )

        dictTargetDependency[operationObj.componentId] = operationObj.requirement

    elif isinstance(operationObj, Info_ProjectDependency_Operation_ChangeRequirement):
        strExistingRequirement = dictTargetDependency.get(operationObj.componentId)
        if strExistingRequirement is None:
            _raise_invalid_plan_input(
                "Only a direct Project dependency can have its requirement changed.",
                {"componentId": operationObj.componentId},
            )

        if strExistingRequirement == operationObj.requirement:
            _raise_invalid_plan_input(
                "The new Component requirement is the same as the current requirement.",
                {
                    "componentId": operationObj.componentId,
                    "requirement": operationObj.requirement,
                },
            )

        dictTargetDependency[operationObj.componentId] = operationObj.requirement

    elif isinstance(operationObj, Info_ProjectDependency_Operation_Remove):
        if operationObj.componentId not in dictTargetDependency:
            _raise_invalid_plan_input(
                "Only a direct Project dependency can be removed.",
                {"componentId": operationObj.componentId},
            )

        del dictTargetDependency[operationObj.componentId]

    elif isinstance(operationObj, Info_ProjectDependency_Operation_Update):
        pass

    else:
        assert_never(operationObj)

    return _replace_manifest_dependencies(
        sourceManifestObj,
        dictTargetDependency,
    )


def _resolve_target_components_lock(
    targetManifestObj: Info_ProjectManifest,
    repositoryIndex: DictRepository_Index,
    operationObj: Info_ProjectDependency_Operation,
    sourceComponentsLock: DictComponentsLock_File | None,
) -> DictComponentsLock_File | None:
    if isinstance(operationObj, Info_ProjectDependency_Operation_Update):
        return resolve_project_dependencies(
            targetManifestObj,
            repositoryIndex,
            existingLock=sourceComponentsLock,
            updateComponentIdSet=set(operationObj.componentIds),
        )

    if not targetManifestObj.componentDependencies:
        return None

    return resolve_project_dependencies(
        targetManifestObj,
        repositoryIndex,
        existingLock=sourceComponentsLock,
    )


def _get_direct_dependency_changes(
    sourceManifestObj: Info_ProjectManifest,
    targetManifestObj: Info_ProjectManifest,
) -> list[DictProjectDependency_DirectChange]:
    dictSourceDependency = sourceManifestObj.componentDependencies
    dictTargetDependency = targetManifestObj.componentDependencies
    listChange: list[DictProjectDependency_DirectChange] = []

    for strComponentId in sorted(set(dictSourceDependency) | set(dictTargetDependency)):
        strPreviousRequirement = dictSourceDependency.get(strComponentId)
        strTargetRequirement = dictTargetDependency.get(strComponentId)

        if strPreviousRequirement is None:
            assert strTargetRequirement is not None
            listChange.append({
                "componentId": strComponentId,
                "change": "added",
                "targetRequirement": strTargetRequirement,
            })
            continue

        if strTargetRequirement is None:
            listChange.append({
                "componentId": strComponentId,
                "change": "removed",
                "previousRequirement": strPreviousRequirement,
            })
            continue

        if strPreviousRequirement != strTargetRequirement:
            listChange.append({
                "componentId": strComponentId,
                "change": "requirementChanged",
                "previousRequirement": strPreviousRequirement,
                "targetRequirement": strTargetRequirement,
            })

    return listChange


def _get_resolved_component_changes(
    sourceComponentsLock: DictComponentsLock_File | None,
    targetComponentsLock: DictComponentsLock_File | None,
) -> list[DictProjectDependency_ResolvedChange]:
    dictSourceComponent: dict[str, DictComponentsLock_Component] = (
        sourceComponentsLock["components"] if sourceComponentsLock is not None else {}
    )
    dictTargetComponent: dict[str, DictComponentsLock_Component] = (
        targetComponentsLock["components"] if targetComponentsLock is not None else {}
    )
    listChange: list[DictProjectDependency_ResolvedChange] = []

    for strComponentId in sorted(set(dictSourceComponent) | set(dictTargetComponent)):
        dictPreviousComponent = dictSourceComponent.get(strComponentId)
        dictTargetComponentEntry = dictTargetComponent.get(strComponentId)

        if dictPreviousComponent is None:
            assert dictTargetComponentEntry is not None
            listChange.append({
                "componentId": strComponentId,
                "packageName": dictTargetComponentEntry["packageName"],
                "displayName": dictTargetComponentEntry["displayName"],
                "change": "added",
                "targetVersion": dictTargetComponentEntry["version"],
            })
            continue

        if dictTargetComponentEntry is None:
            listChange.append({
                "componentId": strComponentId,
                "packageName": dictPreviousComponent["packageName"],
                "displayName": dictPreviousComponent["displayName"],
                "change": "removed",
                "previousVersion": dictPreviousComponent["version"],
            })
            continue

        previousVersionObj = Version(dictPreviousComponent["version"])
        targetVersionObj = Version(dictTargetComponentEntry["version"])
        strChange: Str_ProjectDependency_ResolvedChange
        if previousVersionObj < targetVersionObj:
            strChange = "upgraded"
        elif previousVersionObj > targetVersionObj:
            strChange = "downgraded"
        elif dictPreviousComponent != dictTargetComponentEntry:
            raise ComponentManagementError(
                code="immutable_version_conflict",
                message=(
                    "components.lock.json and the Component Repository contain different content "
                    "for the same Component version."
                ),
                details={
                    "componentId": strComponentId,
                    "version": dictTargetComponentEntry["version"],
                    "lockedSha256": dictPreviousComponent["sha256"],
                    "repositorySha256": dictTargetComponentEntry["sha256"],
                },
            )
        else:
            continue

        dictChange: DictProjectDependency_ResolvedChange = {
            "componentId": strComponentId,
            "packageName": dictTargetComponentEntry["packageName"],
            "displayName": dictTargetComponentEntry["displayName"],
            "change": strChange,
            "previousVersion": dictPreviousComponent["version"],
            "targetVersion": dictTargetComponentEntry["version"],
        }
        listChange.append(dictChange)

    return listChange


def _build_operation_dict(
    operationObj: Info_ProjectDependency_Operation,
) -> dict[str, object]:
    if isinstance(operationObj, Info_ProjectDependency_Operation_Add):
        return {
            "operation": "addComponentDependency",
            "componentId": operationObj.componentId,
            "requirement": operationObj.requirement,
        }

    if isinstance(operationObj, Info_ProjectDependency_Operation_Update):
        return {
            "operation": "updateComponents",
            "componentIds": list(operationObj.componentIds),
        }

    if isinstance(operationObj, Info_ProjectDependency_Operation_ChangeRequirement):
        return {
            "operation": "changeComponentRequirement",
            "componentId": operationObj.componentId,
            "requirement": operationObj.requirement,
        }

    if isinstance(operationObj, Info_ProjectDependency_Operation_Remove):
        return {
            "operation": "removeComponentDependency",
            "componentId": operationObj.componentId,
        }

    assert_never(operationObj)


def _calculate_plan_sha256(
    operationObj: Info_ProjectDependency_Operation,
    sourceManifestObj: Info_ProjectManifest,
    sourceComponentsLock: DictComponentsLock_File | None,
    targetManifestObj: Info_ProjectManifest,
    targetComponentsLock: DictComponentsLock_File | None,
    directDependencyChangeList: list[DictProjectDependency_DirectChange],
    resolvedComponentChangeList: list[DictProjectDependency_ResolvedChange],
) -> str:
    dictHashInput: dict[str, object] = {
        "schemaVersion": 1,
        "operation": _build_operation_dict(operationObj),
        "source": {
            "manifest": build_project_manifest_dict(sourceManifestObj),
            "componentsLock": sourceComponentsLock,
        },
        "target": {
            "manifest": build_project_manifest_dict(targetManifestObj),
            "componentsLock": targetComponentsLock,
        },
        "directDependencyChanges": directDependencyChangeList,
        "resolvedComponentChanges": resolvedComponentChangeList,
    }
    return sha256(serialize_json(dictHashInput, compact=True).encode("utf-8")).hexdigest()


def build_project_dependency_plan(
    manifestObj: Info_ProjectManifest,
    repositoryIndex: DictRepository_Index,
    operationObj: Info_ProjectDependency_Operation,
    *,
    existingLock: DictComponentsLock_File | None = None,
) -> Info_ProjectDependency_Plan:
    """Build a deterministic dependency plan without modifying the Project or Repository."""
    sourceManifestObj = _replace_manifest_dependencies(
        manifestObj,
        manifestObj.componentDependencies,
    )
    dictSourceComponentsLock = _normalize_source_components_lock(
        sourceManifestObj,
        existingLock,
    )
    normalizedOperationObj = _normalize_dependency_operation(operationObj)
    targetManifestObj = _build_target_manifest(
        sourceManifestObj,
        normalizedOperationObj,
    )
    dictTargetComponentsLock = _resolve_target_components_lock(
        targetManifestObj,
        repositoryIndex,
        normalizedOperationObj,
        dictSourceComponentsLock,
    )
    listDirectDependencyChange = _get_direct_dependency_changes(
        sourceManifestObj,
        targetManifestObj,
    )
    listResolvedComponentChange = _get_resolved_component_changes(
        dictSourceComponentsLock,
        dictTargetComponentsLock,
    )
    strPlanSha256 = _calculate_plan_sha256(
        normalizedOperationObj,
        sourceManifestObj,
        dictSourceComponentsLock,
        targetManifestObj,
        dictTargetComponentsLock,
        listDirectDependencyChange,
        listResolvedComponentChange,
    )

    return Info_ProjectDependency_Plan(
        operation=normalizedOperationObj,
        sourceManifest=sourceManifestObj,
        sourceComponentsLock=dictSourceComponentsLock,
        targetManifest=targetManifestObj,
        targetComponentsLock=dictTargetComponentsLock,
        directDependencyChanges=listDirectDependencyChange,
        resolvedComponentChanges=listResolvedComponentChange,
        planSha256=strPlanSha256,
    )
