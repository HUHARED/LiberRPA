# FileName: _Repository.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._BasicConfig import get_basic_config_dict
from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import write_json_atomic
from liberrpa.ComponentManagement.Utils._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    DictComponentManagementWarning,
    WheelBuildResult,
    ComponentWheelInfo,
    DictRepositoryComponentVersion,
    DictRepositoryIndex,
    DictRepositoryTransaction,
    RepositoryPublishResult,
    RepositoryRebuildResult,
)
from liberrpa.ComponentManagement.Utils._Validation import path_exists, file_invalid, folder_invalid
from liberrpa.ComponentManagement._Wheel import inspect_component_wheel
from liberrpa.ComponentManagement.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement._RepositoryIndex import (
    STR_INDEX_FILE_NAME,
    get_repository_components_path,
    get_wheel_path,
    raise_rebuild_required,
    load_repository_index,
    write_repository_index,
    find_equivalent_version,
    add_version_to_index,
)
from liberrpa.ComponentManagement._RepositoryTransaction import (
    remove_transaction_folder,
    get_repository_staging_path,
    recover_publish_transactions,
    copy_wheel_to_staging,
    validate_publish_transactions_for_rebuild,
)

from pathlib import Path
from packaging.version import Version
import os
import uuid


"""
The file structure:

ComponentRepository/
├── repository.json
├── components/
│   ├── ComponentName1_uuidv4/
│   │   ├── componentname1-1.4.2-py313-none-any.whl
│   │   ├── componentname1-1.5.0-py313-none-any.whl
│   │   └── componentname1-2.0.0-py313-none-any.whl
│   └── ComponentName2_uuidv4/
│       └── componentname2-2.3.1-py313-none-any.whl
└── .staging/
    └── publish_<Transaction UUID>/
    ├── transaction.json
    └── candidate.whl  # Present only before the Wheel is committed.
"""


def get_repository_path() -> Path:
    try:
        dictBasicConfig = get_basic_config_dict(toolName="Editor")

        pathRepository = Path(dictBasicConfig["componentRepositoryPath"]).expanduser()

        if not pathRepository.is_absolute():
            raise ComponentManagementError(
                code="repository_unavailable",
                message=("componentRepositoryPath must be an absolute path."),
            )

        pathRepository = pathRepository.resolve()
    except ComponentManagementError:
        raise

    except (OSError, RuntimeError, ValueError) as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message="Failed to read the Component Repository path from basic.jsonc.",
        ) from e

    if not pathRepository.is_dir():
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Component Repository folder was not found: {pathRepository}",
        )

    return pathRepository


def load_repository_resolution_snapshot() -> tuple[
    DictRepositoryIndex,
    list[DictComponentManagementWarning],
]:
    """Read a consistent Repository index snapshot after recovering interrupted publishes."""
    pathRepository = get_repository_path()

    with repository_lock(
        repositoryPath=pathRepository,
        operation="resolveProjectDependencies",
    ):
        listWarning = recover_publish_transactions(pathRepository)
        dictIndex = load_repository_index(pathRepository, checkWheelPaths=True)

    return dictIndex, listWarning


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


def publish_component_wheel(
    manifestObj: ComponentManifest,
    wheelResult: WheelBuildResult,
) -> RepositoryPublishResult:
    pathRepository = get_repository_path()

    with repository_lock(repositoryPath=pathRepository, operation="publishComponent"):
        pathComponents = get_repository_components_path(pathRepository)
        pathStaging = get_repository_staging_path(pathRepository)

        try:
            pathComponents.mkdir(exist_ok=True)
            pathStaging.mkdir(exist_ok=True)
        except OSError as e:
            raise ComponentManagementError(
                code="repository_unavailable",
                message=f"Failed to initialize the Component Repository structure: {pathRepository}",
            ) from e

        listWarning = recover_publish_transactions(pathRepository)
        dictIndex = load_repository_index(pathRepository, checkWheelPaths=True)
        dictComponent = dictIndex["components"].get(manifestObj.id)
        dictVersionEntry = _build_version_entry(manifestObj, wheelResult)

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
            None if dictComponent is None else find_equivalent_version(dictComponent, manifestObj.version)
        )
        if dictExistingVersion is not None:
            pathExistingWheel = get_wheel_path(
                repositoryPath=pathRepository,
                componentId=manifestObj.id,
                packageName=manifestObj.packageName,
                wheelFile=dictExistingVersion["wheelFile"],
            )
            if file_invalid(pathExistingWheel):
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
                if dictExistingVersion != dictVersionEntry:
                    raise_rebuild_required(
                        "The Component version metadata in repository.json does not match the stored Wheel.",
                        {
                            "componentId": manifestObj.id,
                            "version": manifestObj.version,
                            "existingVersionEntry": dictExistingVersion,
                            "expectedVersionEntry": dictVersionEntry,
                        },
                    )

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
        pathTransaction = pathStaging / f"publish_{strTransactionId}"
        pathCandidate = pathTransaction / "candidate.whl"
        pathTargetWheel = get_wheel_path(
            repositoryPath=pathRepository,
            componentId=manifestObj.id,
            packageName=manifestObj.packageName,
            wheelFile=wheelResult.wheelFile,
        )
        strTargetRelativePath = pathTargetWheel.relative_to(pathRepository).as_posix()
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
            copy_wheel_to_staging(wheelResult.wheelPath, pathCandidate)

            if calculate_file_sha256(pathCandidate) != wheelResult.sha256:
                raise ComponentManagementError(
                    code="wheel_sha256_mismatch",
                    message="The Component Wheel changed while it was copied into Repository staging.",
                )

            write_json_atomic(pathTransaction / "transaction.json", dictTransaction)
            pathTargetWheel.parent.mkdir(parents=True, exist_ok=True)

            if path_exists(pathTargetWheel):
                raise_rebuild_required(
                    "An unindexed Component Wheel already exists at the publish target.",
                    {"wheelFile": str(pathTargetWheel)},
                )

            os.replace(pathCandidate, pathTargetWheel)
            dictTransaction["state"] = "wheelCommitted"
            write_json_atomic(pathTransaction / "transaction.json", dictTransaction)

            add_version_to_index(
                indexDict=dictIndex,
                componentId=manifestObj.id,
                packageName=manifestObj.packageName,
                versionEntry=dictVersionEntry,
            )
            write_repository_index(pathRepository, dictIndex)
        except ComponentManagementError:
            raise
        except OSError as e:
            raise ComponentManagementError(
                code="io_error",
                message="Failed to publish the Component Wheel to the Component Repository.",
                details={"repositoryPath": str(pathRepository)},
            ) from e

        dictWarning: DictComponentManagementWarning | None = remove_transaction_folder(pathTransaction)
        if dictWarning is not None:
            listWarning.append(dictWarning)

        return RepositoryPublishResult(
            status="published",
            warnings=listWarning,
        )


def _build_version_entry_from_wheel(
    wheelInfo: ComponentWheelInfo,
) -> DictRepositoryComponentVersion:
    manifestObj = wheelInfo.manifest
    return {
        "version": manifestObj.version,
        "displayName": manifestObj.displayName,
        "description": manifestObj.description,
        "manifestSchemaVersion": manifestObj.schemaVersion,
        "wheelFile": wheelInfo.wheelFile,
        "sha256": wheelInfo.sha256,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dict(sorted(manifestObj.componentDependencies.items())),
    }


def _add_rebuild_issue(
    issueList: list[dict[str, object]],
    *,
    code: str,
    path: Path,
    message: str,
    details: dict[str, object] | None = None,
) -> None:
    dictIssue: dict[str, object] = {
        "code": code,
        "path": str(path),
        "message": message,
    }
    if details is not None:
        dictIssue["details"] = details

    issueList.append(dictIssue)


def rebuild_repository_index() -> RepositoryRebuildResult:
    pathRepository = get_repository_path()

    with repository_lock(repositoryPath=pathRepository, operation="rebuildRepositoryIndex"):
        pathComponents = get_repository_components_path(pathRepository)
        pathStaging = get_repository_staging_path(pathRepository)

        try:
            pathComponents.mkdir(exist_ok=True)
            pathStaging.mkdir(exist_ok=True)
        except OSError as e:
            raise ComponentManagementError(
                code="repository_unavailable",
                message=(f"Failed to initialize the Component Repository structure: {pathRepository}"),
            ) from e

        if folder_invalid(pathComponents):
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="The Component Repository components path is invalid.",
                details={"path": str(pathComponents)},
            )

        dictNewIndex: DictRepositoryIndex = {
            "schemaVersion": 1,
            "components": {},
        }
        listIssue: list[dict[str, object]] = []
        listWarning: list[DictComponentManagementWarning] = []
        dictVersionPath: dict[tuple[str, Version], Path] = {}

        for pathComponentFolder in sorted(pathComponents.iterdir(), key=lambda pathObj: pathObj.name):
            if folder_invalid(pathComponentFolder):
                _add_rebuild_issue(
                    listIssue,
                    code="invalid_component_folder",
                    path=pathComponentFolder,
                    message="Repository components may contain only Component folders.",
                )
                continue

            listWheelPath: list[Path] = []
            boolHasUnexpectedEntry = False

            for pathEntry in sorted(pathComponentFolder.iterdir(), key=lambda pathObj: pathObj.name):
                if file_invalid(pathEntry) or pathEntry.suffix.casefold() != ".whl":
                    boolHasUnexpectedEntry = True
                    _add_rebuild_issue(
                        listIssue,
                        code="unexpected_repository_entry",
                        path=pathEntry,
                        message="A Component Repository folder may contain only Wheel files.",
                    )
                    continue

                listWheelPath.append(pathEntry)

            if not listWheelPath and not boolHasUnexpectedEntry:
                listWarning.append({
                    "code": "empty_component_repository_folder",
                    "message": f"Ignored empty Component Repository folder: {pathComponentFolder}",
                })
                continue

            for pathWheel in listWheelPath:
                try:
                    wheelInfo = inspect_component_wheel(pathWheel)
                except ComponentManagementError as e:
                    _add_rebuild_issue(
                        listIssue,
                        code=e.code,
                        path=pathWheel,
                        message=e.message,
                        details=e.details,
                    )
                    continue

                manifestObj = wheelInfo.manifest
                strExpectedFolderName = f"{manifestObj.packageName}_{manifestObj.id}"
                if pathComponentFolder.name != strExpectedFolderName:
                    _add_rebuild_issue(
                        listIssue,
                        code="component_folder_mismatch",
                        path=pathWheel,
                        message=(f"Wheel is stored in the wrong Component folder. Expected {strExpectedFolderName!r}."),
                    )
                    continue

                tupleVersionKey = (manifestObj.id, Version(manifestObj.version))
                pathExistingVersion = dictVersionPath.get(tupleVersionKey)
                if pathExistingVersion is not None:
                    _add_rebuild_issue(
                        listIssue,
                        code="duplicate_component_version",
                        path=pathWheel,
                        message=(
                            "Repository contains more than one Wheel for the same Component ID and PEP 440 equivalent version."
                        ),
                        details={"existingWheel": str(pathExistingVersion)},
                    )
                    continue

                dictVersionPath[tupleVersionKey] = pathWheel
                dictVersionEntry = _build_version_entry_from_wheel(wheelInfo)

                try:
                    add_version_to_index(
                        indexDict=dictNewIndex,
                        componentId=manifestObj.id,
                        packageName=manifestObj.packageName,
                        versionEntry=dictVersionEntry,
                    )
                except ComponentManagementError as e:
                    _add_rebuild_issue(
                        listIssue,
                        code=e.code,
                        path=pathWheel,
                        message=e.message,
                        details=e.details,
                    )

        if listIssue:
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message=("Repository index could not be rebuilt because one or more Repository entries are invalid."),
                details={"issues": listIssue},
            )

        listTransactionCleanup = validate_publish_transactions_for_rebuild(
            repositoryPath=pathRepository,
            indexDict=dictNewIndex,
        )

        try:
            write_repository_index(pathRepository, dictNewIndex)
        except OSError as e:
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="Failed to write the rebuilt Component Repository index.",
                details={"indexFile": str(pathRepository / STR_INDEX_FILE_NAME)},
            ) from e

        for pathTransaction in listTransactionCleanup:
            dictWarning = remove_transaction_folder(pathTransaction)
            if dictWarning is not None:
                listWarning.append(dictWarning)

        intVersionCount = sum(len(dictComponent["versions"]) for dictComponent in dictNewIndex["components"].values())

        return RepositoryRebuildResult(
            componentCount=len(dictNewIndex["components"]),
            versionCount=intVersionCount,
            warnings=listWarning,
        )
