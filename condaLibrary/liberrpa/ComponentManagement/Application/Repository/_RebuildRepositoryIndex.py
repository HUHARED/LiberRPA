# FileName: _RebuildRepositoryIndex.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Validation import (
    is_file_invalid,
    is_folder_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_Index,
    Info_Repository_RebuildResult,
)
from liberrpa.ComponentManagement.Domain.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Domain.Wheel._Wheel import inspect_component_wheel
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    STR_INDEX_FILE_NAME,
    write_repository_index,
    add_version_to_index,
)
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import (
    get_repository_path,
)
from liberrpa.ComponentManagement.Domain.Repository._Structure import (
    initialize_repository_structure,
)
from liberrpa.ComponentManagement.Domain.Repository._TransactionStorage import (
    remove_repository_transaction_folder,
)
from liberrpa.ComponentManagement.Domain.Repository._PublishTransaction import (
    validate_publish_transactions_for_rebuild,
)
from liberrpa.ComponentManagement.Domain.Repository._ImportTransaction import (
    validate_import_transactions_for_rebuild,
)
from liberrpa.ComponentManagement.Domain.Repository._VersionEntry import (
    build_repository_version_entry,
)

from pathlib import Path
from packaging.version import Version


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
        "message": message,
        "path": str(path),
    }
    if details is not None:
        dictIssue["details"] = details

    issueList.append(dictIssue)


def rebuild_repository_index() -> Info_Repository_RebuildResult:
    """
    Rebuild repository.json from the Component Wheels stored in the Repository.

    When scanning each Component folder, Wheel files and unexpected entries are
    classified as follows:

    - No Wheel files and no unexpected entries:
        The folder is truly empty. Add an "empty_component_repository_folder" warning and ignore the folder.

    - No Wheel files but unexpected entries exist:
        The folder is not empty and must not be reported as an empty Component folder.
        Handle the unexpected entries according to their own validation rules.

    - Wheel files exist and no unexpected entries exist:
        Process the Wheel files normally when rebuilding the Repository index.

    - Wheel files and unexpected entries both exist:
        Do not classify the folder as empty.
        Process the Wheel files and handle the unexpected entries according to their respective validation rules.

    An unexpected entry is an item that is not accepted as a Component Wheel in the current Component folder, such as an unrelated file, nested folder, or symbolic link.
    """
    pathRepository = get_repository_path()

    with repository_lock(pathRepository, "rebuildRepositoryIndex"):
        pathComponents, _ = initialize_repository_structure(pathRepository)

        if is_folder_invalid(pathComponents):
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="The Component Repository components path is invalid.",
                details={"path": str(pathComponents)},
            )

        dictNewIndex: DictRepository_Index = {
            "schemaVersion": 1,
            "components": {},
        }
        listIssue: list[dict[str, object]] = []
        listWarning: list[DictComponentManagementWarning] = []
        dictVersionPath: dict[tuple[str, Version], Path] = {}

        for pathComponentFolder in sorted(
            pathComponents.iterdir(), key=lambda pathObj: pathObj.name
        ):
            if is_folder_invalid(pathComponentFolder):
                _add_rebuild_issue(
                    listIssue,
                    code="invalid_component_folder",
                    path=pathComponentFolder,
                    message="Repository components may contain only Component folders.",
                )
                continue

            listWheelPath: list[Path] = []
            boolHasUnexpectedEntry = False

            for pathEntry in sorted(
                pathComponentFolder.iterdir(), key=lambda pathObj: pathObj.name
            ):
                if is_file_invalid(pathEntry) or pathEntry.suffix.casefold() != ".whl":
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
                    wheelInfoObj = inspect_component_wheel(pathWheel)
                except ComponentManagementError as e:
                    _add_rebuild_issue(
                        listIssue,
                        code=e.code,
                        path=pathWheel,
                        message=e.message,
                        details=e.details,
                    )
                    continue

                manifestObj = wheelInfoObj.manifest
                strExpectedFolderName = f"{manifestObj.packageName}_{manifestObj.id}"
                if pathComponentFolder.name != strExpectedFolderName:
                    _add_rebuild_issue(
                        listIssue,
                        code="component_folder_mismatch",
                        path=pathWheel,
                        message=(
                            f"Wheel is stored in the wrong Component folder. Expected {strExpectedFolderName!r}."
                        ),
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

                dictVersionEntry = build_repository_version_entry(
                    manifestObj=wheelInfoObj.manifest,
                    wheelFileName=wheelInfoObj.wheelFileName,
                    sha256=wheelInfoObj.sha256,
                )

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
                message=(
                    "Repository index could not be rebuilt because one or more Repository entries are invalid."
                ),
                details={"issues": listIssue},
            )

        listTransactionCleanup = validate_publish_transactions_for_rebuild(
            repositoryPath=pathRepository,
            indexDict=dictNewIndex,
        )
        listTransactionCleanup.extend(
            validate_import_transactions_for_rebuild(
                repositoryPath=pathRepository,
                indexDict=dictNewIndex,
            )
        )

        try:
            write_repository_index(pathRepository, dictNewIndex)
        except OSError as e:
            raise ComponentManagementError(
                code="repository_rebuild_failed",
                message="Failed to write the rebuilt Component Repository index.",
                details={"indexFile": str(pathRepository / STR_INDEX_FILE_NAME)},
            ) from e

        for pathTransactionFolder in listTransactionCleanup:
            dictWarning = remove_repository_transaction_folder(pathTransactionFolder)
            if dictWarning is not None:
                listWarning.append(dictWarning)

        intVersionCount = sum(
            len(dictComponent["versions"])
            for dictComponent in dictNewIndex["components"].values()
        )

        return Info_Repository_RebuildResult(
            componentCount=len(dictNewIndex["components"]),
            versionCount=intVersionCount,
            warnings=listWarning,
        )
