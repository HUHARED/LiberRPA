# FileName: _ComponentsLock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import read_json, write_json_atomic
from liberrpa.ComponentManagement.Common._Version import normalize_version, normalize_specifier
from liberrpa.ComponentManagement.Common._Validation import (
    get_package_name_error,
    validate_exact_keys,
    path_exists,
    is_file_invalid,
)
from liberrpa.ComponentManagement.Types._Manifest import (
    Info_ProjectManifest_Flow,
    Info_ProjectManifest,
)
from liberrpa.ComponentManagement.Types._Components import (
    DictComponentsLock_Root_FlowProject,
    DictComponentsLock_Root_ComponentProject,
    DictComponentsLock_Root,
    DictComponentsLock_Component,
    DictComponentsLock_File,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    validate_wheel_file_name,
    validate_sha256,
    normalize_component_id,
    validate_component_dependency_dict,
)

from pathlib import Path
from packaging.specifiers import SpecifierSet
from packaging.version import Version


STR_COMPONENTS_LOCK_FILE_NAME = "components.lock.json"

_SET_COMPONENTS_LOCK_KEYS = {"schemaVersion", "root", "components"}
_SET_FLOW_ROOT_KEYS = {
    "manifestFile",
    "requiresLiberrpa",
    "componentDependencies",
}
_SET_COMPONENT_ROOT_KEYS = {
    *_SET_FLOW_ROOT_KEYS,
    "componentId",
    "packageName",
}
_SET_LOCKED_COMPONENT_KEYS = {
    "packageName",
    "displayName",
    "version",
    "wheelFile",
    "sha256",
    "requiresLiberrpa",
    "componentDependencies",
}


def _validate_components_lock_root(value: object) -> DictComponentsLock_Root:
    if not isinstance(value, dict):
        raise ValueError("components.lock.json root must be an object.")

    manifestFile = value.get("manifestFile")
    if manifestFile == "flow.json":
        validate_exact_keys(value, _SET_FLOW_ROOT_KEYS, "root")
    elif manifestFile == "component.json":
        validate_exact_keys(value, _SET_COMPONENT_ROOT_KEYS, "root")
    else:
        raise ValueError("root.manifestFile must be 'flow.json' or 'component.json'.")

    rootComponentId: str | None = None
    packageName: str | None = None

    if manifestFile == "component.json":
        rootComponentId = normalize_component_id(value.get("componentId"), "root.componentId")

        packageNameValue = value.get("packageName")
        if not isinstance(packageNameValue, str):
            raise ValueError("root.packageName must be a string.")
        strPackageNameError = get_package_name_error(packageNameValue)
        if strPackageNameError is not None:
            raise ValueError(f"root.packageName: {strPackageNameError}")
        packageName = packageNameValue

    requiresLiberrpa = value.get("requiresLiberrpa")
    if not isinstance(requiresLiberrpa, str):
        raise ValueError("root.requiresLiberrpa must be a string.")
    strNormalizedRequiresLiberrpa = normalize_specifier(requiresLiberrpa)
    if requiresLiberrpa != strNormalizedRequiresLiberrpa:
        raise ValueError("root.requiresLiberrpa must use the normalized version range.")

    dictDependency = validate_component_dependency_dict(
        value.get("componentDependencies"),
        "root.componentDependencies",
        componentId=rootComponentId,
    )

    if manifestFile == "flow.json":
        return {
            "manifestFile": "flow.json",
            "requiresLiberrpa": strNormalizedRequiresLiberrpa,
            "componentDependencies": dictDependency,
        }

    assert rootComponentId is not None
    assert packageName is not None
    return {
        "manifestFile": "component.json",
        "componentId": rootComponentId,
        "packageName": packageName,
        "requiresLiberrpa": strNormalizedRequiresLiberrpa,
        "componentDependencies": dictDependency,
    }


def _validate_dependency_graph(
    rootDict: DictComponentsLock_Root,
    componentDict: dict[str, DictComponentsLock_Component],
) -> None:
    strRootComponentId = rootDict["componentId"] if rootDict["manifestFile"] == "component.json" else None

    for strDependencyId, strSpecifier in rootDict["componentDependencies"].items():
        dictDependency = componentDict.get(strDependencyId)
        if dictDependency is None:
            raise ValueError(f"root.componentDependencies refers to missing Component {strDependencyId!r}.")

        if not SpecifierSet(strSpecifier).contains(Version(dictDependency["version"]), prereleases=True):
            raise ValueError(
                f"Locked Component {strDependencyId} {dictDependency['version']} does not satisfy root requirement {strSpecifier!r}."
            )

    for strComponentId, dictComponent in componentDict.items():
        for strDependencyId, strSpecifier in dictComponent["componentDependencies"].items():
            if strRootComponentId is not None and strDependencyId == strRootComponentId:
                raise ValueError(
                    f"Locked Component {strComponentId} depends on the root Component and creates a dependency cycle."
                )

            dictDependency = componentDict.get(strDependencyId)
            if dictDependency is None:
                raise ValueError(f"Locked Component {strComponentId} refers to missing Component {strDependencyId!r}.")

            if not SpecifierSet(strSpecifier).contains(Version(dictDependency["version"]), prereleases=True):
                raise ValueError(
                    f"Locked Component {strDependencyId} {dictDependency['version']} does not satisfy "
                    f"requirement {strSpecifier!r} from Component {strComponentId}."
                )

    setVisited: set[str] = set()
    setVisiting: set[str] = set()
    listVisitPath: list[str] = []

    def visit_component(componentId: str) -> None:
        if componentId in setVisited:
            return

        if componentId in setVisiting:
            intCycleStart = listVisitPath.index(componentId)
            listCycle = [*listVisitPath[intCycleStart:], componentId]
            raise ValueError(f"components.lock.json contains a dependency cycle: {' -> '.join(listCycle)}.")

        setVisiting.add(componentId)
        listVisitPath.append(componentId)

        for dependencyId in componentDict[componentId]["componentDependencies"]:
            visit_component(dependencyId)

        listVisitPath.pop()
        setVisiting.remove(componentId)
        setVisited.add(componentId)

    for strComponentId in componentDict:
        visit_component(strComponentId)

    setReachable: set[str] = set()

    def collect_reachable(componentId: str) -> None:
        if componentId in setReachable:
            return

        setReachable.add(componentId)
        for dependencyId in componentDict[componentId]["componentDependencies"]:
            collect_reachable(dependencyId)

    for strDependencyId in rootDict["componentDependencies"]:
        collect_reachable(strDependencyId)

    listUnreachable = sorted(set(componentDict) - setReachable)
    if listUnreachable:
        raise ValueError(f"components.lock.json contains unreachable Components: {listUnreachable}.")


def _validate_locked_component(
    value: object,
    field: str,
    *,
    componentId: str,
) -> DictComponentsLock_Component:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    validate_exact_keys(value, _SET_LOCKED_COMPONENT_KEYS, field)

    packageName = value.get("packageName")
    if not isinstance(packageName, str):
        raise ValueError(f"{field}.packageName must be a string.")
    strPackageNameError = get_package_name_error(packageName)
    if strPackageNameError is not None:
        raise ValueError(f"{field}.packageName: {strPackageNameError}")

    displayName = value.get("displayName")
    if not isinstance(displayName, str) or displayName.strip() == "":
        raise ValueError(f"{field}.displayName must be a non-empty string.")
    if displayName != displayName.strip() or "\r" in displayName or "\n" in displayName:
        raise ValueError(f"{field}.displayName must be a trimmed single-line string.")

    version = value.get("version")
    if not isinstance(version, str):
        raise ValueError(f"{field}.version must be a string.")
    strNormalizedVersion = normalize_version(version)
    if version != strNormalizedVersion:
        raise ValueError(f"{field}.version must use the normalized PEP 440 form.")

    strWheelFile = validate_wheel_file_name(
        value.get("wheelFile"),
        f"{field}.wheelFile",
        packageName=packageName,
        version=strNormalizedVersion,
    )
    strSha256 = validate_sha256(value.get("sha256"), f"{field}.sha256")

    requiresLiberrpa = value.get("requiresLiberrpa")
    if not isinstance(requiresLiberrpa, str):
        raise ValueError(f"{field}.requiresLiberrpa must be a string.")
    strNormalizedRequiresLiberrpa = normalize_specifier(requiresLiberrpa)
    if requiresLiberrpa != strNormalizedRequiresLiberrpa:
        raise ValueError(f"{field}.requiresLiberrpa must use the normalized version range.")

    dictDependency = validate_component_dependency_dict(
        value.get("componentDependencies"),
        f"{field}.componentDependencies",
        componentId=componentId,
    )

    return {
        "packageName": packageName,
        "displayName": displayName,
        "version": strNormalizedVersion,
        "wheelFile": strWheelFile,
        "sha256": strSha256,
        "requiresLiberrpa": strNormalizedRequiresLiberrpa,
        "componentDependencies": dictDependency,
    }


def validate_components_lock(value: object) -> DictComponentsLock_File:
    if not isinstance(value, dict):
        raise ValueError("components.lock.json root value must be an object.")

    validate_exact_keys(value, _SET_COMPONENTS_LOCK_KEYS, "components.lock.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("components.lock.json schemaVersion must be 1.")

    dictRoot = _validate_components_lock_root(value.get("root"))

    componentsValue = value.get("components")
    if not isinstance(componentsValue, dict):
        raise ValueError("components.lock.json components must be an object.")

    dictComponent: dict[str, DictComponentsLock_Component] = {}
    dictPackageOwner: dict[str, str] = {}

    if dictRoot["manifestFile"] == "component.json":
        dictPackageOwner[dictRoot["packageName"].casefold()] = "root Component"
        strRootComponentId: str | None = dictRoot["componentId"]
    else:
        strRootComponentId = None

    for componentId, componentValue in componentsValue.items():
        strComponentId = normalize_component_id(componentId, f"components.{componentId}")
        if strRootComponentId is not None and strComponentId == strRootComponentId:
            raise ValueError("components cannot contain the root Component ID.")

        dictLockedComponent = _validate_locked_component(
            componentValue,
            f"components.{strComponentId}",
            componentId=strComponentId,
        )

        strPackageKey = dictLockedComponent["packageName"].casefold()
        strExistingPackageOwner = dictPackageOwner.get(strPackageKey)
        if strExistingPackageOwner is not None:
            raise ValueError(
                f"Package name {dictLockedComponent['packageName']!r} is already used by {strExistingPackageOwner}."
            )

        dictPackageOwner[strPackageKey] = f"Component {strComponentId}"
        dictComponent[strComponentId] = dictLockedComponent

    dictComponent = dict(sorted(dictComponent.items()))
    _validate_dependency_graph(dictRoot, dictComponent)

    return {
        "schemaVersion": 1,
        "root": dictRoot,
        "components": dictComponent,
    }


def _build_components_lock_root(manifestObj: Info_ProjectManifest) -> DictComponentsLock_Root:
    dictDependency = dict(sorted(manifestObj.componentDependencies.items()))

    if isinstance(manifestObj, Info_ProjectManifest_Flow):
        dictFlowRoot: DictComponentsLock_Root_FlowProject = {
            "manifestFile": "flow.json",
            "requiresLiberrpa": manifestObj.requiresLiberrpa,
            "componentDependencies": dictDependency,
        }
        return dictFlowRoot

    dictComponentRoot: DictComponentsLock_Root_ComponentProject = {
        "manifestFile": "component.json",
        "componentId": manifestObj.id,
        "packageName": manifestObj.packageName,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dictDependency,
    }
    return dictComponentRoot


def build_components_lock(
    manifestObj: Info_ProjectManifest,
    componentDict: dict[str, DictComponentsLock_Component],
) -> DictComponentsLock_File:
    return validate_components_lock({
        "schemaVersion": 1,
        "root": _build_components_lock_root(manifestObj),
        "components": componentDict,
    })


def read_components_lock(lockPath: Path) -> DictComponentsLock_File:
    if not path_exists(lockPath):
        raise ComponentManagementError(
            code="components_lock_missing",
            message=f"Components lock file was not found: {lockPath}",
        )

    if is_file_invalid(lockPath):
        raise ComponentManagementError(
            code="components_lock_invalid",
            message=f"Components lock path is invalid: {lockPath}",
        )

    try:
        return validate_components_lock(read_json(lockPath))
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="components_lock_invalid",
            message="Invalid components.lock.json.",
            details={"lockFile": str(lockPath), "reason": str(e)},
        ) from e


def write_components_lock(lockPath: Path, lockDict: DictComponentsLock_File) -> None:
    try:
        dictValidatedLock = validate_components_lock(lockDict)
        write_json_atomic(lockPath, dictValidatedLock)
    except ValueError as e:
        raise ComponentManagementError(
            code="components_lock_invalid",
            message="Cannot write an invalid components.lock.json.",
            details={"lockFile": str(lockPath), "reason": str(e)},
        ) from e
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to write components.lock.json: {lockPath}",
        ) from e


def is_components_lock_stale(
    lockDict: DictComponentsLock_File,
    manifestObj: Info_ProjectManifest,
) -> bool:
    return lockDict["root"] != _build_components_lock_root(manifestObj)
