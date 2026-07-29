# FileName: _RepositoryIndex.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_json, write_json_atomic
from liberrpa.ComponentManagement.Utils._TypedValue import (
    DictRepositoryComponentVersion,
    DictRepositoryComponent,
    DictRepositoryIndex,
)
from liberrpa.ComponentManagement.Utils._Version import normalize_specifier, normalize_version
from liberrpa.ComponentManagement.Utils._Validation import get_package_name_error, validate_exact_keys
from liberrpa.ComponentManagement.Utils._WheelName import (
    STR_COMPONENT_WHEEL_TAG,
    TAG_COMPONENT_WHEEL,
    get_component_wheel_names,
)

from pathlib import Path, PurePosixPath
from packaging.version import Version
from packaging.utils import (
    InvalidWheelFilename,
    canonicalize_name,
    parse_wheel_filename,
)
import re
import uuid


STR_INDEX_FILE_NAME = "repository.json"
_STR_COMPONENT_FOLDER_NAME = "components"

_REGEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_SET_REPOSITORY_INDEX_KEYS = {"schemaVersion", "components"}
_SET_REPOSITORY_COMPONENT_KEYS = {"packageName", "versions"}
_SET_REPOSITORY_VERSION_KEYS = {
    "version",
    "displayName",
    "description",
    "manifestSchemaVersion",
    "wheelFile",
    "sha256",
    "requiresLiberrpa",
    "componentDependencies",
}


def validate_wheel_file_name(
    value: object,
    field: str,
    *,
    packageName: str,
    version: str,
) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field} must be a non-empty string.")

    if "/" in value or "\\" in value or Path(value).name != value:
        raise ValueError(f"{field} must be a Wheel filename without folder separators.")

    try:
        normalizedName, wheelVersion, buildTag, tagSet = parse_wheel_filename(value)
    except InvalidWheelFilename as e:
        raise ValueError(f"{field} must be a valid Wheel filename.") from e

    if normalizedName != canonicalize_name(packageName):
        raise ValueError(f"{field} distribution name does not match packageName {packageName!r}.")

    if wheelVersion != Version(version):
        raise ValueError(f"{field} version does not match version {version!r}.")

    if buildTag:
        raise ValueError(f"{field} cannot contain a Wheel build tag.")

    if tagSet != frozenset({TAG_COMPONENT_WHEEL}):
        raise ValueError(f"{field} must use the {STR_COMPONENT_WHEEL_TAG} tag.")

    _, strExpectedFileName = get_component_wheel_names(packageName, version)

    if value != strExpectedFileName:
        raise ValueError(f"{field} must use the normalized filename {strExpectedFileName!r}.")

    return value


def validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _REGEX_SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 value.")

    return value


def normalize_component_id(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string.")

    try:
        uuidObj = uuid.UUID(value)
    except ValueError as e:
        raise ValueError(f"{field} must be a valid UUID.") from e

    if uuidObj.version != 4 or uuidObj.variant != uuid.RFC_4122:
        raise ValueError(f"{field} must be a UUID v4.")

    strNormalizedId = str(uuidObj)
    if value != strNormalizedId:
        raise ValueError(f"{field} must use the normalized lowercase UUID form.")

    return strNormalizedId


def validate_component_dependency_dict(
    value: object,
    field: str,
    *,
    componentId: str | None,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    dictDependency: dict[str, str] = {}

    for dependencyId, specifier in value.items():
        strDependencyId = normalize_component_id(dependencyId, f"{field}.{dependencyId}")
        if componentId is not None and strDependencyId == componentId:
            raise ValueError(f"{field} cannot contain a self-dependency.")

        if not isinstance(specifier, str):
            raise ValueError(f"{field}.{strDependencyId} must be a string.")

        strNormalizedSpecifier = normalize_specifier(specifier)
        if specifier != strNormalizedSpecifier:
            raise ValueError(f"{field}.{strDependencyId} must use the normalized version range.")

        dictDependency[strDependencyId] = strNormalizedSpecifier

    return dict(sorted(dictDependency.items()))


def validate_repository_version(
    value: object,
    field: str,
    *,
    componentId: str,
    packageName: str,
) -> DictRepositoryComponentVersion:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    validate_exact_keys(value, _SET_REPOSITORY_VERSION_KEYS, field)

    version = value.get("version")
    if not isinstance(version, str):
        raise ValueError(f"{field}.version must be a string.")
    strNormalizedVersion = normalize_version(version)
    if version != strNormalizedVersion:
        raise ValueError(f"{field}.version must use the normalized PEP 440 form.")

    displayName = value.get("displayName")
    if not isinstance(displayName, str) or displayName.strip() == "":
        raise ValueError(f"{field}.displayName must be a non-empty string.")
    if displayName != displayName.strip() or "\r" in displayName or "\n" in displayName:
        raise ValueError(f"{field}.displayName must be a trimmed single-line string.")

    description = value.get("description")
    if not isinstance(description, str):
        raise ValueError(f"{field}.description must be a string.")

    manifestSchemaVersion = value.get("manifestSchemaVersion")
    if type(manifestSchemaVersion) is not int or manifestSchemaVersion != 1:
        raise ValueError(f"{field}.manifestSchemaVersion must be 1.")

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
        "version": strNormalizedVersion,
        "displayName": displayName,
        "description": description,
        "manifestSchemaVersion": manifestSchemaVersion,
        "wheelFile": strWheelFile,
        "sha256": strSha256,
        "requiresLiberrpa": strNormalizedRequiresLiberrpa,
        "componentDependencies": dictDependency,
    }


def _validate_repository_index(value: object) -> DictRepositoryIndex:
    if not isinstance(value, dict):
        raise ValueError("repository.json root value must be an object.")

    validate_exact_keys(value, _SET_REPOSITORY_INDEX_KEYS, "repository.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("repository.json schemaVersion must be 1.")

    components = value.get("components")
    if not isinstance(components, dict):
        raise ValueError("repository.json components must be an object.")

    dictComponent: dict[str, DictRepositoryComponent] = {}

    for componentId, componentValue in components.items():
        strComponentId = normalize_component_id(componentId, f"components.{componentId}")
        if not isinstance(componentValue, dict):
            raise ValueError(f"components.{strComponentId} must be an object.")

        validate_exact_keys(
            componentValue,
            _SET_REPOSITORY_COMPONENT_KEYS,
            f"components.{strComponentId}",
        )

        packageName = componentValue.get("packageName")
        if not isinstance(packageName, str):
            raise ValueError(f"components.{strComponentId}.packageName must be a string.")
        strPackageNameError = get_package_name_error(packageName)
        if strPackageNameError is not None:
            raise ValueError(f"components.{strComponentId}.packageName: {strPackageNameError}")

        versions = componentValue.get("versions")
        if not isinstance(versions, list):
            raise ValueError(f"components.{strComponentId}.versions must be an array.")
        if not versions:
            raise ValueError(f"components.{strComponentId}.versions cannot be empty.")

        listVersion: list[DictRepositoryComponentVersion] = []
        setVersion: set[Version] = set()

        for intIndex, versionValue in enumerate(versions):
            dictVersion = validate_repository_version(
                versionValue,
                f"components.{strComponentId}.versions[{intIndex}]",
                componentId=strComponentId,
                packageName=packageName,
            )
            versionObj = Version(dictVersion["version"])
            if versionObj in setVersion:
                raise ValueError(f"components.{strComponentId}.versions contains equivalent PEP 440 versions.")

            setVersion.add(versionObj)
            listVersion.append(dictVersion)

        listVersion.sort(key=lambda item: Version(item["version"]))
        dictComponent[strComponentId] = {
            "packageName": packageName,
            "versions": listVersion,
        }

    return {
        "schemaVersion": 1,
        "components": dict(sorted(dictComponent.items())),
    }


def get_repository_components_path(repositoryPath: Path) -> Path:
    return repositoryPath / _STR_COMPONENT_FOLDER_NAME


def get_wheel_relative_path(
    componentId: str,
    packageName: str,
    wheelFile: str,
) -> str:
    return PurePosixPath(
        _STR_COMPONENT_FOLDER_NAME,
        f"{packageName}_{componentId}",
        wheelFile,
    ).as_posix()


def get_wheel_path(
    repositoryPath: Path,
    componentId: str,
    packageName: str,
    wheelFile: str,
) -> Path:
    return repositoryPath.joinpath(
        *PurePosixPath(
            get_wheel_relative_path(
                componentId=componentId,
                packageName=packageName,
                wheelFile=wheelFile,
            )
        ).parts
    )


def _get_expected_wheel_path_set(indexDict: DictRepositoryIndex) -> set[str]:
    setWheelPath: set[str] = set()

    for strComponentId, dictComponent in indexDict["components"].items():
        for dictVersion in dictComponent["versions"]:
            setWheelPath.add(
                get_wheel_relative_path(
                    componentId=strComponentId,
                    packageName=dictComponent["packageName"],
                    wheelFile=dictVersion["wheelFile"],
                )
            )

    return setWheelPath


def raise_rebuild_required(message: str, details: dict[str, object] | None = None) -> None:
    raise ComponentManagementError(
        code="repository_rebuild_required",
        message=message,
        details=details,
    )


def _get_actual_wheel_path_set(repositoryPath: Path) -> set[str]:
    pathComponents = get_repository_components_path(repositoryPath)
    if not pathComponents.exists():
        return set()

    if not pathComponents.is_dir() or pathComponents.is_symlink():
        raise_rebuild_required(
            "The Component Repository components path is not a valid folder.",
            {"path": str(pathComponents)},
        )

    setWheelPath: set[str] = set()

    for pathWheel in pathComponents.rglob("*.whl"):
        if not pathWheel.is_file() or pathWheel.is_symlink():
            raise_rebuild_required(
                "The Component Repository contains an invalid Wheel path.",
                {"wheelFile": str(pathWheel)},
            )

        setWheelPath.add(pathWheel.relative_to(repositoryPath).as_posix())

    return setWheelPath


def load_repository_index(
    repositoryPath: Path,
    *,
    checkWheelPaths: bool,
) -> DictRepositoryIndex:
    pathIndexFile = repositoryPath / STR_INDEX_FILE_NAME

    if not pathIndexFile.exists():
        dictIndex: DictRepositoryIndex = {
            "schemaVersion": 1,
            "components": {},
        }
    elif not pathIndexFile.is_file() or pathIndexFile.is_symlink():
        raise_rebuild_required(
            "Component Repository index is invalid.",
            {"indexFile": str(pathIndexFile)},
        )
    else:
        try:
            dictIndex = _validate_repository_index(read_json(pathIndexFile))
        except (OSError, ValueError) as e:
            raise_rebuild_required(
                "Component Repository index is invalid and must be rebuilt.",
                {"indexFile": str(pathIndexFile), "reason": str(e)},
            )

    if checkWheelPaths:
        setExpectedPath = _get_expected_wheel_path_set(dictIndex)
        setActualPath = _get_actual_wheel_path_set(repositoryPath)

        if setExpectedPath != setActualPath:
            raise_rebuild_required(
                "Component Repository index does not match the stored Wheels.",
                {
                    "missingWheels": sorted(setExpectedPath - setActualPath),
                    "unindexedWheels": sorted(setActualPath - setExpectedPath),
                },
            )

    return dictIndex


def write_repository_index(repositoryPath: Path, indexDict: DictRepositoryIndex) -> None:
    write_json_atomic(repositoryPath / STR_INDEX_FILE_NAME, indexDict)


def find_equivalent_version(
    componentDict: DictRepositoryComponent,
    version: str,
) -> DictRepositoryComponentVersion | None:
    targetVersion = Version(version)

    for dictVersionEntry in componentDict["versions"]:
        if Version(dictVersionEntry["version"]) == targetVersion:
            return dictVersionEntry

    return None


def add_version_to_index(
    indexDict: DictRepositoryIndex,
    componentId: str,
    packageName: str,
    versionEntry: DictRepositoryComponentVersion,
) -> None:
    dictComponent: DictRepositoryComponent | None = indexDict["components"].get(componentId)

    if dictComponent is None:
        dictComponent = {
            "packageName": packageName,
            "versions": [],
        }
        indexDict["components"][componentId] = dictComponent
    elif dictComponent["packageName"] != packageName:
        raise ComponentManagementError(
            code="component_identity_conflict",
            message=(f"Component ID {componentId} is already bound to packageName {dictComponent['packageName']!r}."),
            details={
                "componentId": componentId,
                "existingPackageName": dictComponent["packageName"],
                "publishedPackageName": packageName,
            },
        )

    dictExistingVersion = find_equivalent_version(dictComponent, versionEntry["version"])
    if dictExistingVersion is not None:
        if dictExistingVersion["sha256"] != versionEntry["sha256"]:
            raise ComponentManagementError(
                code="immutable_version_conflict",
                message=(f"Component {packageName} {versionEntry['version']} already exists with different content."),
                details={
                    "componentId": componentId,
                    "version": versionEntry["version"],
                    "existingSha256": dictExistingVersion["sha256"],
                    "publishedSha256": versionEntry["sha256"],
                },
            )
        return

    dictComponent["versions"].append(versionEntry)
    dictComponent["versions"].sort(key=lambda item: Version(item["version"]))
    indexDict["components"] = dict(sorted(indexDict["components"].items()))
