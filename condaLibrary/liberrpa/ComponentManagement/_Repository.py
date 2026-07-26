# FileName: _Repository.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._BasicConfig import get_basic_config_dict
from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import read_json, write_json_atomic
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    WheelBuildResult,
    DictRepositoryComponentVersion,
    DictRepositoryComponent,
    DictRepositoryIndex,
    DictRepositoryTransaction,
    RepositoryPublishResult,
)
from liberrpa.ComponentManagement.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Utils._Version import normalize_specifier, normalize_version
from liberrpa.ComponentManagement.Utils._Validation import raise_rebuild_required

from pathlib import Path, PurePosixPath
from typing import cast
from packaging.version import Version
import os
import re
import shutil
import uuid

"""
The file structure:

ComponentRepository/
├── repository.json
├── components/
│   ├── ComponentName1_uuidv4/
│   │   ├── compoentname1-1.4.2-py313-none-any.whl
│   │   ├── compoentname1-1.5.0-py313-none-any.whl
│   │   └── compoentname1-2.0.0-py313-none-any.whl
│   └── ComponentName2_uuidv4/
│       └── compoentname2-2.3.1-py313-none-any.whl
└── .staging/

"""

_STR_INDEX_FILE_NAME = "repository.json"
_STR_COMPONENT_FOLDER_NAME = "components"
_STR_STAGING_FOLDER_NAME = ".staging"

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
_SET_TRANSACTION_KEYS = {
    "schemaVersion",
    "operation",
    "state",
    "componentId",
    "packageName",
    "version",
    "wheelFile",
    "sha256",
    "targetRelativePath",
    "versionEntry",
}


def _validate_exact_keys(value: dict[object, object], expectedKey: set[str], field: str) -> None:
    setStringKey = {key for key in value if isinstance(key, str)}
    listNonStringKey = sorted(repr(key) for key in value if not isinstance(key, str))
    listMissingKey = sorted(expectedKey - setStringKey)
    listUnknownKey = sorted(setStringKey - expectedKey)

    if listNonStringKey or listMissingKey or listUnknownKey:
        raise ValueError(
            f"{field} has invalid fields. Missing: {listMissingKey}; "
            f"unknown: {listUnknownKey}; non-string: {listNonStringKey}."
        )


def _validate_wheel_file_name(value: object, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field} must be a non-empty string.")

    if "/" in value or "\\" in value or Path(value).name != value or not value.endswith(".whl"):
        raise ValueError(f"{field} must be a Wheel filename without folder separators.")

    return value


def _validate_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _REGEX_SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 value.")

    return value


def _normalize_component_id(value: object, field: str) -> str:
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


def _validate_dependency_dict(
    value: object,
    field: str,
    *,
    componentId: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    dictDependency: dict[str, str] = {}

    for dependencyId, specifier in value.items():
        strDependencyId = _normalize_component_id(dependencyId, f"{field}.{dependencyId}")
        if strDependencyId == componentId:
            raise ValueError(f"{field} cannot contain a self-dependency.")

        if not isinstance(specifier, str):
            raise ValueError(f"{field}.{strDependencyId} must be a string.")

        strNormalizedSpecifier = normalize_specifier(specifier)
        if specifier != strNormalizedSpecifier:
            raise ValueError(f"{field}.{strDependencyId} must use the normalized version range.")

        dictDependency[strDependencyId] = strNormalizedSpecifier

    return dict(sorted(dictDependency.items()))


def _validate_repository_version(
    value: object,
    field: str,
    *,
    componentId: str,
) -> DictRepositoryComponentVersion:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    _validate_exact_keys(value, _SET_REPOSITORY_VERSION_KEYS, field)

    version = value.get("version")
    if not isinstance(version, str):
        raise ValueError(f"{field}.version must be a string.")
    strNormalizedVersion = normalize_version(version)
    if version != strNormalizedVersion:
        raise ValueError(f"{field}.version must use the normalized PEP 440 form.")

    displayName = value.get("displayName")
    if not isinstance(displayName, str) or displayName == "":
        raise ValueError(f"{field}.displayName must be a non-empty string.")

    description = value.get("description")
    if not isinstance(description, str):
        raise ValueError(f"{field}.description must be a string.")

    manifestSchemaVersion = value.get("manifestSchemaVersion")
    if type(manifestSchemaVersion) is not int or manifestSchemaVersion != 1:
        raise ValueError(f"{field}.manifestSchemaVersion must be 1.")

    strWheelFile = _validate_wheel_file_name(value.get("wheelFile"), f"{field}.wheelFile")
    strSha256 = _validate_sha256(value.get("sha256"), f"{field}.sha256")

    requiresLiberrpa = value.get("requiresLiberrpa")
    if not isinstance(requiresLiberrpa, str):
        raise ValueError(f"{field}.requiresLiberrpa must be a string.")
    strNormalizedRequiresLiberrpa = normalize_specifier(requiresLiberrpa)
    if requiresLiberrpa != strNormalizedRequiresLiberrpa:
        raise ValueError(f"{field}.requiresLiberrpa must use the normalized version range.")

    dictDependency = _validate_dependency_dict(
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

    _validate_exact_keys(value, _SET_REPOSITORY_INDEX_KEYS, "repository.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("repository.json schemaVersion must be 1.")

    components = value.get("components")
    if not isinstance(components, dict):
        raise ValueError("repository.json components must be an object.")

    dictComponent: dict[str, DictRepositoryComponent] = {}

    for componentId, componentValue in components.items():
        strComponentId = _normalize_component_id(componentId, f"components.{componentId}")
        if not isinstance(componentValue, dict):
            raise ValueError(f"components.{strComponentId} must be an object.")

        _validate_exact_keys(
            componentValue,
            _SET_REPOSITORY_COMPONENT_KEYS,
            f"components.{strComponentId}",
        )

        packageName = componentValue.get("packageName")
        if not isinstance(packageName, str) or packageName == "":
            raise ValueError(f"components.{strComponentId}.packageName must be a non-empty string.")

        versions = componentValue.get("versions")
        if not isinstance(versions, list):
            raise ValueError(f"components.{strComponentId}.versions must be an array.")

        listVersion: list[DictRepositoryComponentVersion] = []
        setVersion: set[Version] = set()

        for intIndex, versionValue in enumerate(versions):
            dictVersion = _validate_repository_version(
                versionValue,
                f"components.{strComponentId}.versions[{intIndex}]",
                componentId=strComponentId,
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


def _get_component_folder_name(packageName: str, componentId: str) -> str:
    return f"{packageName}_{componentId}"


def _get_wheel_relative_path(
    componentId: str,
    packageName: str,
    wheelFile: str,
) -> str:
    return PurePosixPath(
        _STR_COMPONENT_FOLDER_NAME,
        _get_component_folder_name(packageName, componentId),
        wheelFile,
    ).as_posix()


def _get_expected_wheel_path_set(index: DictRepositoryIndex) -> set[str]:
    setWheelPath: set[str] = set()

    for strComponentId, dictComponent in index["components"].items():
        for dictVersion in dictComponent["versions"]:
            setWheelPath.add(
                _get_wheel_relative_path(
                    componentId=strComponentId,
                    packageName=dictComponent["packageName"],
                    wheelFile=dictVersion["wheelFile"],
                )
            )

    return setWheelPath


def _get_actual_wheel_path_set(repositoryPath: Path) -> set[str]:
    pathComponents = repositoryPath / _STR_COMPONENT_FOLDER_NAME
    if not pathComponents.exists():
        return set()

    if not pathComponents.is_dir():
        raise_rebuild_required(
            "The Component Repository components path is not a folder.",
            {"path": str(pathComponents)},
        )

    return {
        pathWheel.relative_to(repositoryPath).as_posix()
        for pathWheel in pathComponents.rglob("*.whl")
        if pathWheel.is_file()
    }


def _load_repository_index(
    repositoryPath: Path,
    *,
    checkWheelPaths: bool,
) -> DictRepositoryIndex:
    pathIndexFile = repositoryPath / _STR_INDEX_FILE_NAME

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


def _find_equivalent_version(
    componentDict: DictRepositoryComponent,
    version: str,
) -> DictRepositoryComponentVersion | None:
    targetVersion = Version(version)

    for dictVersionEntry in componentDict["versions"]:
        if Version(dictVersionEntry["version"]) == targetVersion:
            return dictVersionEntry

    return None


def _add_version_to_index(
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

    dictExistingVersion = _find_equivalent_version(dictComponent, versionEntry["version"])
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


def _validate_transaction(value: object) -> DictRepositoryTransaction:
    if not isinstance(value, dict):
        raise ValueError("Transaction root value must be an object.")

    _validate_exact_keys(value, _SET_TRANSACTION_KEYS, "transaction.json")

    if value.get("schemaVersion") != 1 or value.get("operation") != "publishComponent":
        raise ValueError("Unsupported Repository transaction.")

    state = value.get("state")
    if state not in {"prepared", "wheelCommitted"}:
        raise ValueError("Invalid Repository transaction state.")

    strComponentId = _normalize_component_id(value.get("componentId"), "componentId")

    packageName = value.get("packageName")
    if not isinstance(packageName, str) or packageName == "":
        raise ValueError("packageName must be a non-empty string.")

    version = value.get("version")
    if not isinstance(version, str) or normalize_version(version) != version:
        raise ValueError("version must use the normalized PEP 440 form.")

    strWheelFile = _validate_wheel_file_name(value.get("wheelFile"), "wheelFile")
    strSha256 = _validate_sha256(value.get("sha256"), "sha256")

    targetRelativePath = value.get("targetRelativePath")
    if not isinstance(targetRelativePath, str):
        raise ValueError("targetRelativePath must be a string.")

    strExpectedRelativePath = _get_wheel_relative_path(
        componentId=strComponentId,
        packageName=packageName,
        wheelFile=strWheelFile,
    )
    if targetRelativePath != strExpectedRelativePath:
        raise ValueError("targetRelativePath does not match the Component identity.")

    dictVersionEntry = _validate_repository_version(
        value.get("versionEntry"),
        "versionEntry",
        componentId=strComponentId,
    )
    if (
        dictVersionEntry["version"] != version
        or dictVersionEntry["wheelFile"] != strWheelFile
        or dictVersionEntry["sha256"] != strSha256
    ):
        raise ValueError("Transaction versionEntry does not match the transaction fields.")

    return cast(
        DictRepositoryTransaction,
        {
            "schemaVersion": 1,
            "operation": "publishComponent",
            "state": state,
            "componentId": strComponentId,
            "packageName": packageName,
            "version": version,
            "wheelFile": strWheelFile,
            "sha256": strSha256,
            "targetRelativePath": targetRelativePath,
            "versionEntry": dictVersionEntry,
        },
    )


def _remove_transaction_folder(transactionPath: Path) -> dict[str, object] | None:
    try:
        shutil.rmtree(transactionPath)
    except OSError as e:
        return {
            "code": "repository_cleanup_pending",
            "message": f"Published successfully, but temporary Repository files could not be removed: {transactionPath}",
            "details": {"reason": str(e)},
        }

    return None


def _recover_publish_transactions(repositoryPath: Path) -> list[dict[str, object]]:
    pathStaging = repositoryPath / _STR_STAGING_FOLDER_NAME
    if not pathStaging.exists():
        return []

    if not pathStaging.is_dir():
        raise ComponentManagementError(
            code="repository_recovery_failed",
            message=f"Component Repository staging path is invalid: {pathStaging}",
        )

    listWarning: list[dict[str, object]] = []
    dictIndex = _load_repository_index(repositoryPath, checkWheelPaths=False)

    for pathTransaction in sorted(pathStaging.glob("publish_*"), key=lambda pathObj: pathObj.name):
        if not pathTransaction.is_dir():
            continue

        pathTransactionFile = pathTransaction / "transaction.json"
        if not pathTransactionFile.is_file():
            dictWarning = _remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)
            continue

        try:
            dictTransaction = _validate_transaction(read_json(pathTransactionFile))
        except (OSError, ValueError) as e:
            raise ComponentManagementError(
                code="repository_recovery_failed",
                message=f"Invalid Component Repository transaction: {pathTransactionFile}",
                details={"reason": str(e)},
            ) from e

        pathTargetWheel = repositoryPath.joinpath(*PurePosixPath(dictTransaction["targetRelativePath"]).parts)
        dictComponent = dictIndex["components"].get(dictTransaction["componentId"])
        dictExistingVersion = (
            None if dictComponent is None else _find_equivalent_version(dictComponent, dictTransaction["version"])
        )

        if pathTargetWheel.is_file():
            strActualSha256 = calculate_file_sha256(pathTargetWheel)
            if strActualSha256 != dictTransaction["sha256"]:
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message="A committed Component Wheel does not match its interrupted transaction.",
                    details={
                        "wheelFile": str(pathTargetWheel),
                        "expectedSha256": dictTransaction["sha256"],
                        "actualSha256": strActualSha256,
                    },
                )

            if dictExistingVersion is None:
                try:
                    _add_version_to_index(
                        indexDict=dictIndex,
                        componentId=dictTransaction["componentId"],
                        packageName=dictTransaction["packageName"],
                        versionEntry=dictTransaction["versionEntry"],
                    )
                    write_json_atomic(repositoryPath / _STR_INDEX_FILE_NAME, dictIndex)
                except ComponentManagementError as e:
                    raise ComponentManagementError(
                        code="repository_recovery_failed",
                        message="The Repository index conflicts with an interrupted publish transaction.",
                        details={"transactionFile": str(pathTransactionFile)},
                    ) from e
                except OSError as e:
                    raise ComponentManagementError(
                        code="repository_recovery_failed",
                        message="Failed to finish an interrupted Component Repository publish transaction.",
                    ) from e
            elif dictExistingVersion["sha256"] != dictTransaction["sha256"]:
                raise ComponentManagementError(
                    code="repository_recovery_failed",
                    message="The Repository index conflicts with an interrupted publish transaction.",
                    details={"transactionFile": str(pathTransactionFile)},
                )
        elif dictExistingVersion is not None:
            raise ComponentManagementError(
                code="repository_recovery_failed",
                message="The Repository index references a Wheel missing from an interrupted transaction.",
                details={"wheelFile": str(pathTargetWheel)},
            )

        dictWarning = _remove_transaction_folder(pathTransaction)
        if dictWarning is not None:
            listWarning.append(dictWarning)

    return listWarning


def _get_repository_path() -> Path:
    try:
        dictBasicConfig = get_basic_config_dict(toolName="Editor")
        repositoryPath = Path(dictBasicConfig["componentRepositoryPath"]).expanduser().resolve()
    except (OSError, ValueError) as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message="Failed to read the Component Repository path from basic.jsonc.",
        ) from e

    if not repositoryPath.is_dir():
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Component Repository folder was not found: {repositoryPath}",
        )

    return repositoryPath


def _get_wheel_path(
    repositoryPath: Path,
    componentId: str,
    packageName: str,
    wheelFileName: str,
) -> Path:
    return (
        repositoryPath
        / _STR_COMPONENT_FOLDER_NAME
        / _get_component_folder_name(packageName, componentId)
        / wheelFileName
    )


def _build_version_entry(
    manifestObj: ComponentManifest,
    wheelResult: WheelBuildResult,
) -> DictRepositoryComponentVersion:
    return {
        "version": manifestObj.version,
        "displayName": manifestObj.displayName,
        "description": manifestObj.description,
        "manifestSchemaVersion": manifestObj.schemaVersion,
        "wheelFile": wheelResult.wheelFile,
        "sha256": wheelResult.sha256,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dict(sorted(manifestObj.componentDependencies.items())),
    }


def _copy_wheel_to_staging(sourcePath: Path, targetPath: Path) -> None:
    try:
        with sourcePath.open("rb") as sourceFileObj, targetPath.open("xb") as targetFileObj:
            shutil.copyfileobj(sourceFileObj, targetFileObj, length=1024 * 1024)
            targetFileObj.flush()
            os.fsync(targetFileObj.fileno())
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to copy the Component Wheel into Repository staging: {targetPath}",
        ) from e


def publish_component_wheel(
    manifestObj: ComponentManifest,
    wheelResult: WheelBuildResult,
) -> RepositoryPublishResult:
    pathRepository = _get_repository_path()

    with repository_lock(repositoryPath=pathRepository, operation="publishComponent"):
        try:
            (pathRepository / _STR_COMPONENT_FOLDER_NAME).mkdir(exist_ok=True)
            (pathRepository / _STR_STAGING_FOLDER_NAME).mkdir(exist_ok=True)
        except OSError as e:
            raise ComponentManagementError(
                code="repository_unavailable",
                message=f"Failed to initialize the Component Repository structure: {pathRepository}",
            ) from e

        listWarning = _recover_publish_transactions(pathRepository)
        dictIndex = _load_repository_index(pathRepository, checkWheelPaths=True)
        dictComponent = dictIndex["components"].get(manifestObj.id)

        if dictComponent is not None and dictComponent["packageName"] != manifestObj.packageName:
            raise ComponentManagementError(
                code="component_identity_conflict",
                message=(
                    f"Component ID {manifestObj.id} is already bound to packageName {dictComponent['packageName']!r}."
                ),
                details={
                    "componentId": manifestObj.id,
                    "existingPackageName": dictComponent["packageName"],
                    "publishedPackageName": manifestObj.packageName,
                },
            )

        dictExistingVersion = (
            None if dictComponent is None else _find_equivalent_version(dictComponent, manifestObj.version)
        )
        if dictExistingVersion is not None:
            pathExistingWheel = _get_wheel_path(
                repositoryPath=pathRepository,
                componentId=manifestObj.id,
                packageName=manifestObj.packageName,
                wheelFileName=dictExistingVersion["wheelFile"],
            )
            if not pathExistingWheel.is_file():
                raise_rebuild_required(
                    "A Component Wheel referenced by repository.json is missing.",
                    {"wheelFile": str(pathExistingWheel)},
                )

            strExistingSha256 = calculate_file_sha256(pathExistingWheel)
            if strExistingSha256 != dictExistingVersion["sha256"]:
                raise_rebuild_required(
                    "A Component Wheel does not match the SHA-256 stored in repository.json.",
                    {
                        "wheelFile": str(pathExistingWheel),
                        "expectedSha256": dictExistingVersion["sha256"],
                        "actualSha256": strExistingSha256,
                    },
                )

            if strExistingSha256 == wheelResult.sha256:
                return RepositoryPublishResult(
                    status="alreadyPublished",
                    warnings=listWarning,
                )

            raise ComponentManagementError(
                code="immutable_version_conflict",
                message=(
                    f"Component {manifestObj.displayName} {manifestObj.version} is already published with different content. Change component.json version before publishing again."
                ),
                details={
                    "componentId": manifestObj.id,
                    "version": manifestObj.version,
                    "existingSha256": strExistingSha256,
                    "publishedSha256": wheelResult.sha256,
                },
            )

        strBuiltSha256 = calculate_file_sha256(wheelResult.wheelPath)
        if strBuiltSha256 != wheelResult.sha256:
            raise ComponentManagementError(
                code="wheel_sha256_mismatch",
                message="The built Component Wheel changed before it was published.",
                details={
                    "wheelFile": str(wheelResult.wheelPath),
                    "expectedSha256": wheelResult.sha256,
                    "actualSha256": strBuiltSha256,
                },
            )

        strTransactionId = str(uuid.uuid4())
        pathTransaction = pathRepository / _STR_STAGING_FOLDER_NAME / f"publish_{strTransactionId}"
        pathCandidate = pathTransaction / "candidate.whl"
        pathTargetWheel = _get_wheel_path(
            repositoryPath=pathRepository,
            componentId=manifestObj.id,
            packageName=manifestObj.packageName,
            wheelFileName=wheelResult.wheelFile,
        )
        strTargetRelativePath = pathTargetWheel.relative_to(pathRepository).as_posix()
        dictVersionEntry = _build_version_entry(manifestObj, wheelResult)
        dictTransaction: DictRepositoryTransaction = {
            "schemaVersion": 1,
            "operation": "publishComponent",
            "state": "prepared",
            "componentId": manifestObj.id,
            "packageName": manifestObj.packageName,
            "version": manifestObj.version,
            "wheelFile": wheelResult.wheelFile,
            "sha256": wheelResult.sha256,
            "targetRelativePath": strTargetRelativePath,
            "versionEntry": dictVersionEntry,
        }

        try:
            pathTransaction.mkdir(parents=False)
            _copy_wheel_to_staging(wheelResult.wheelPath, pathCandidate)

            if calculate_file_sha256(pathCandidate) != wheelResult.sha256:
                raise ComponentManagementError(
                    code="wheel_sha256_mismatch",
                    message="The Component Wheel changed while it was copied into Repository staging.",
                )

            write_json_atomic(pathTransaction / "transaction.json", dictTransaction)
            pathTargetWheel.parent.mkdir(parents=True, exist_ok=True)

            if pathTargetWheel.exists():
                raise_rebuild_required(
                    "An unindexed Component Wheel already exists at the publish target.",
                    {"wheelFile": str(pathTargetWheel)},
                )

            os.replace(pathCandidate, pathTargetWheel)
            dictTransaction["state"] = "wheelCommitted"
            write_json_atomic(pathTransaction / "transaction.json", dictTransaction)

            _add_version_to_index(
                indexDict=dictIndex,
                componentId=manifestObj.id,
                packageName=manifestObj.packageName,
                versionEntry=dictVersionEntry,
            )
            write_json_atomic(pathRepository / _STR_INDEX_FILE_NAME, dictIndex)
        except ComponentManagementError:
            raise
        except OSError as e:
            raise ComponentManagementError(
                code="io_error",
                message="Failed to publish the Component Wheel to the Component Repository.",
                details={"repositoryPath": str(pathRepository)},
            ) from e

        dictWarning = _remove_transaction_folder(pathTransaction)
        if dictWarning is not None:
            listWarning.append(dictWarning)

        return RepositoryPublishResult(
            status="published",
            warnings=listWarning,
        )
