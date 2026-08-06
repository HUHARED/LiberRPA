# FileName: _ImportComponentWheels.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import write_json_atomic
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._Version import get_installed_liberrpa_version
from liberrpa.ComponentManagement.Common._Validation import (
    path_exists,
    is_file_invalid,
)
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Wheel import Info_ComponentWheel
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_ComponentVersionEntry,
    DictRepository_Index,
    DictRepository_Transaction_ImportArtifact,
    DictRepository_Transaction_Import,
    Info_Repository_Import_ComponentResult,
    Info_Repository_ImportResult,
)
from liberrpa.ComponentManagement.Domain.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Domain.Wheel._Wheel import inspect_component_wheel
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    get_wheel_path,
    load_repository_index,
    write_repository_index,
    find_equivalent_version,
    add_version_to_index,
)
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import (
    get_repository_path,
)
from liberrpa.ComponentManagement.Domain.Repository._Structure import (
    initialize_repository_structure,
)
from liberrpa.ComponentManagement.Domain.Repository._Transaction import (
    recover_repository_transactions,
)
from liberrpa.ComponentManagement.Domain.Repository._TransactionStorage import (
    copy_wheel_to_staging,
    remove_repository_transaction_folder,
)
from liberrpa.ComponentManagement.Domain.Repository._VersionEntry import (
    build_repository_version_entry,
)

from pathlib import Path, PurePosixPath
from copy import deepcopy
from packaging.specifiers import SpecifierSet
from packaging.version import Version
import os
import uuid


def _resolve_source_wheel_paths(
    sourceWheelPathList: list[Path],
    repositoryPath: Path,
) -> list[Path]:
    if not sourceWheelPathList:
        raise ComponentManagementError(
            code="component_wheel_import_invalid_input",
            message="At least one Component Wheel must be selected for import.",
        )

    listResolvedPath: list[Path] = []
    setResolvedPath: set[str] = set()

    for intIndex, pathSource in enumerate(sourceWheelPathList):
        try:
            pathResolved = pathSource.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise ComponentManagementError(
                code="component_wheel_import_invalid_input",
                message=f"Failed to resolve Component Wheel path at index {intIndex}.",
                details={"sourcePath": str(pathSource)},
            ) from e

        if is_file_invalid(pathResolved) or pathResolved.suffix.casefold() != ".whl":
            raise ComponentManagementError(
                code="component_wheel_import_invalid_input",
                message="Selected Component Wheel path is not a regular .whl file.",
                details={"sourcePath": str(pathResolved)},
            )

        if pathResolved.is_relative_to(repositoryPath):
            raise ComponentManagementError(
                code="component_wheel_import_invalid_input",
                message="A Wheel already inside ComponentRepository cannot be imported as an external Wheel.",
                details={"sourcePath": str(pathResolved)},
            )

        strPathKey = str(pathResolved).casefold()
        if strPathKey in setResolvedPath:
            raise ComponentManagementError(
                code="component_wheel_import_invalid_input",
                message="The same Component Wheel path was selected more than once.",
                details={"sourcePath": str(pathResolved)},
            )

        setResolvedPath.add(strPathKey)
        listResolvedPath.append(pathResolved)

    return listResolvedPath


def _validate_existing_version(
    repositoryPath: Path,
    componentId: str,
    packageName: str,
    versionEntry: DictRepository_ComponentVersionEntry,
    existingVersionEntry: DictRepository_ComponentVersionEntry,
) -> None:
    pathExistingWheel = get_wheel_path(
        repositoryPath=repositoryPath,
        componentId=componentId,
        packageName=packageName,
        wheelFileName=existingVersionEntry["wheelFileName"],
    )
    if is_file_invalid(pathExistingWheel):
        raise ComponentManagementError(
            code="repository_rebuild_required",
            message="A Component Wheel referenced by repository.json is missing or invalid.",
            details={"wheelPath": str(pathExistingWheel)},
        )

    wheelInfo = inspect_component_wheel(pathExistingWheel)
    dictActualVersion = build_repository_version_entry(
        manifestObj=wheelInfo.manifest,
        wheelFileName=wheelInfo.wheelFileName,
        sha256=wheelInfo.sha256,
    )
    if dictActualVersion != existingVersionEntry:
        raise ComponentManagementError(
            code="repository_rebuild_required",
            message="A Component Wheel does not match its metadata in repository.json.",
            details={
                "wheelPath": str(pathExistingWheel),
                "existingVersionEntry": existingVersionEntry,
                "actualVersionEntry": dictActualVersion,
            },
        )

    if existingVersionEntry != versionEntry:
        raise ComponentManagementError(
            code="immutable_version_conflict",
            message=(
                f"Component {packageName} {versionEntry['version']} already exists in ComponentRepository "
                "with different content."
            ),
            details={
                "componentId": componentId,
                "version": versionEntry["version"],
                "existingSha256": existingVersionEntry["sha256"],
                "importedSha256": versionEntry["sha256"],
            },
        )


def _get_import_warnings(
    wheelInfoList: list[Info_ComponentWheel],
    plannedIndex: DictRepository_Index,
) -> list[DictComponentManagementWarning]:
    listWarning: list[DictComponentManagementWarning] = []

    try:
        installedVersionObj = get_installed_liberrpa_version()
    except ValueError as e:
        installedVersionObj = None
        listWarning.append({
            "code": "liberrpa_version_unavailable",
            "message": "The installed liberrpa version could not be determined while importing Component Wheels.",
            "details": {"reason": str(e)},
        })

    for wheelInfo in wheelInfoList:
        manifestObj = wheelInfo.manifest

        if installedVersionObj is not None and not SpecifierSet(
            manifestObj.requiresLiberrpa
        ).contains(installedVersionObj):
            listWarning.append({
                "code": "component_liberrpa_incompatible",
                "message": (
                    f"Imported Component {manifestObj.packageName} {manifestObj.version} requires liberrpa "
                    f"{manifestObj.requiresLiberrpa}, but installed liberrpa is {installedVersionObj}."
                ),
                "details": {
                    "componentId": manifestObj.id,
                    "packageName": manifestObj.packageName,
                    "version": manifestObj.version,
                    "requiresLiberrpa": manifestObj.requiresLiberrpa,
                    "installedLiberrpaVersion": str(installedVersionObj),
                },
            })

        for strDependencyId, strSpecifier in manifestObj.componentDependencies.items():
            dictDependency = plannedIndex["components"].get(strDependencyId)
            boolDependencyAvailable = dictDependency is not None and any(
                SpecifierSet(strSpecifier).contains(
                    Version(dictVersionEntry["version"]),
                    prereleases=True,
                )
                for dictVersionEntry in dictDependency["versions"]
            )
            if boolDependencyAvailable:
                continue

            listWarning.append({
                "code": "component_dependency_unavailable",
                "message": (
                    f"Imported Component {manifestObj.packageName} {manifestObj.version} depends on "
                    f"Component {strDependencyId} {strSpecifier}, which is not currently available in ComponentRepository."
                ),
                "details": {
                    "componentId": manifestObj.id,
                    "packageName": manifestObj.packageName,
                    "version": manifestObj.version,
                    "dependencyId": strDependencyId,
                    "requirement": strSpecifier,
                },
            })

    return listWarning


def import_component_wheels(
    sourceWheelPathList: list[Path],
) -> Info_Repository_ImportResult:
    pathRepository = get_repository_path()
    listSourcePath = _resolve_source_wheel_paths(sourceWheelPathList, pathRepository)

    with repository_lock(pathRepository, "importComponentWheels"):
        _, pathStagingFolder = initialize_repository_structure(pathRepository)

        listWarning = recover_repository_transactions(pathRepository)
        dictIndex = load_repository_index(pathRepository, checkWheelPaths=True)
        dictPlannedIndex = deepcopy(dictIndex)

        strTransactionId = str(uuid.uuid4())
        pathTransaction = pathStagingFolder / f"import_{strTransactionId}"
        pathArtifacts = pathTransaction / "artifacts"
        pathTransactionFile = pathTransaction / "transaction.json"
        boolTransactionRecorded = False

        listWheelInfo: list[Info_ComponentWheel] = []
        listResult: list[Info_Repository_Import_ComponentResult] = []
        listTransactionArtifact: list[DictRepository_Transaction_ImportArtifact] = []
        setBatchVersion: set[tuple[str, Version]] = set()

        try:
            pathArtifacts.mkdir(parents=True)

            for intIndex, pathSource in enumerate(listSourcePath):
                strArtifactRelativePath = f"{intIndex:04d}/{pathSource.name}"
                pathArtifact = pathArtifacts.joinpath(
                    *PurePosixPath(strArtifactRelativePath).parts
                )
                pathArtifact.parent.mkdir()
                copy_wheel_to_staging(pathSource, pathArtifact)
                wheelInfo = inspect_component_wheel(pathArtifact)
                listWheelInfo.append(wheelInfo)

                manifestObj = wheelInfo.manifest
                tupleVersionKey = (manifestObj.id, Version(manifestObj.version))
                if tupleVersionKey in setBatchVersion:
                    raise ComponentManagementError(
                        code="duplicate_component_version",
                        message=(
                            "The selected Wheel batch contains more than one Wheel for the same Component ID "
                            "and PEP 440 equivalent version."
                        ),
                        details={
                            "componentId": manifestObj.id,
                            "version": manifestObj.version,
                            "sourcePath": str(pathSource),
                        },
                    )
                setBatchVersion.add(tupleVersionKey)

                dictVersionEntry = build_repository_version_entry(
                    manifestObj=wheelInfo.manifest,
                    wheelFileName=wheelInfo.wheelFileName,
                    sha256=wheelInfo.sha256,
                )
                dictComponent = dictPlannedIndex["components"].get(manifestObj.id)
                if (
                    dictComponent is not None
                    and dictComponent["packageName"] != manifestObj.packageName
                ):
                    raise ComponentManagementError(
                        code="component_identity_conflict",
                        message=(
                            f"Component ID {manifestObj.id} is already bound to packageName "
                            f"{dictComponent['packageName']!r}."
                        ),
                        details={
                            "componentId": manifestObj.id,
                            "existingPackageName": dictComponent["packageName"],
                            "importedPackageName": manifestObj.packageName,
                        },
                    )

                dictExistingVersion = (
                    None
                    if dictComponent is None
                    else find_equivalent_version(dictComponent, manifestObj.version)
                )

                if dictExistingVersion is not None:
                    _validate_existing_version(
                        pathRepository,
                        manifestObj.id,
                        manifestObj.packageName,
                        dictVersionEntry,
                        dictExistingVersion,
                    )
                    pathArtifact.unlink()
                    listResult.append(
                        Info_Repository_Import_ComponentResult(
                            sourcePath=pathSource,
                            componentId=manifestObj.id,
                            packageName=manifestObj.packageName,
                            version=manifestObj.version,
                            wheelFileName=wheelInfo.wheelFileName,
                            sha256=wheelInfo.sha256,
                            status="alreadyImported",
                        )
                    )
                    continue

                add_version_to_index(
                    indexDict=dictPlannedIndex,
                    componentId=manifestObj.id,
                    packageName=manifestObj.packageName,
                    versionEntry=dictVersionEntry,
                )
                pathTargetWheel = get_wheel_path(
                    repositoryPath=pathRepository,
                    componentId=manifestObj.id,
                    packageName=manifestObj.packageName,
                    wheelFileName=wheelInfo.wheelFileName,
                )
                if path_exists(pathTargetWheel):
                    raise ComponentManagementError(
                        code="repository_rebuild_required",
                        message="An unindexed Component Wheel already exists at an import target.",
                        details={"wheelPath": str(pathTargetWheel)},
                    )

                listTransactionArtifact.append({
                    "artifactRelativePath": strArtifactRelativePath,
                    "componentId": manifestObj.id,
                    "packageName": manifestObj.packageName,
                    "version": manifestObj.version,
                    "wheelFileName": wheelInfo.wheelFileName,
                    "sha256": wheelInfo.sha256,
                    "targetRelativePath": pathTargetWheel.relative_to(
                        pathRepository
                    ).as_posix(),
                    "versionEntry": dictVersionEntry,
                })
                listResult.append(
                    Info_Repository_Import_ComponentResult(
                        sourcePath=pathSource,
                        componentId=manifestObj.id,
                        packageName=manifestObj.packageName,
                        version=manifestObj.version,
                        wheelFileName=wheelInfo.wheelFileName,
                        sha256=wheelInfo.sha256,
                        status="imported",
                    )
                )

            listWarning.extend(_get_import_warnings(listWheelInfo, dictPlannedIndex))

            if not listTransactionArtifact:
                dictCleanupWarning = remove_repository_transaction_folder(pathTransaction)
                if dictCleanupWarning is not None:
                    listWarning.append(dictCleanupWarning)
                return Info_Repository_ImportResult(
                    components=listResult,
                    warnings=listWarning,
                )

            dictTransaction: DictRepository_Transaction_Import = {
                "schemaVersion": 1,
                "operation": "importComponentWheels",
                "state": "prepared",
                "artifacts": listTransactionArtifact,
            }
            write_json_atomic(pathTransactionFile, dictTransaction)
            boolTransactionRecorded = True

            for dictArtifact in listTransactionArtifact:
                pathArtifact = pathArtifacts.joinpath(
                    *PurePosixPath(dictArtifact["artifactRelativePath"]).parts
                )
                if calculate_file_sha256(pathArtifact) != dictArtifact["sha256"]:
                    raise ComponentManagementError(
                        code="wheel_sha256_mismatch",
                        message="A Component Wheel changed while it was prepared for Repository import.",
                        details={"wheelPath": str(pathArtifact)},
                    )

                pathTargetWheel = pathRepository.joinpath(
                    *PurePosixPath(dictArtifact["targetRelativePath"]).parts
                )
                pathTargetWheel.parent.mkdir(parents=True, exist_ok=True)
                if path_exists(pathTargetWheel):
                    raise ComponentManagementError(
                        code="repository_rebuild_required",
                        message="An unindexed Component Wheel appeared at an import target.",
                        details={"wheelPath": str(pathTargetWheel)},
                    )
                os.replace(pathArtifact, pathTargetWheel)

            dictTransaction["state"] = "wheelsCommitted"
            write_json_atomic(pathTransactionFile, dictTransaction)
            write_repository_index(pathRepository, dictPlannedIndex)
        except ComponentManagementError:
            if not boolTransactionRecorded:
                remove_repository_transaction_folder(pathTransaction)
            raise
        except OSError as e:
            if not boolTransactionRecorded:
                remove_repository_transaction_folder(pathTransaction)
            raise ComponentManagementError(
                code="io_error",
                message="Failed to import Component Wheels into ComponentRepository.",
                details={"repositoryPath": str(pathRepository)},
            ) from e

        dictCleanupWarning = remove_repository_transaction_folder(pathTransaction)
        if dictCleanupWarning is not None:
            listWarning.append(dictCleanupWarning)

        return Info_Repository_ImportResult(
            components=listResult,
            warnings=listWarning,
        )
