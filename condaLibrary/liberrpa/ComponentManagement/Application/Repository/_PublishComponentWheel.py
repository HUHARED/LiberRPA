# FileName: _PublishComponentWheel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import write_json_atomic
from liberrpa.ComponentManagement.Common._Hash import calculate_file_sha256
from liberrpa.ComponentManagement.Common._Validation import path_exists, is_file_invalid
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Wheel import Info_ComponentWheel_BuildResult
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_Transaction_Publish,
    Info_Repository_PublishResult,
)
from liberrpa.ComponentManagement.Domain.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    get_wheel_path,
    raise_rebuild_required,
    load_repository_index,
    write_repository_index,
    find_equivalent_version,
    add_version_to_index,
)
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import get_repository_path
from liberrpa.ComponentManagement.Domain.Repository._Structure import initialize_repository_structure
from liberrpa.ComponentManagement.Domain.Repository._Transaction import recover_repository_transactions
from liberrpa.ComponentManagement.Domain.Repository._TransactionStorage import (
    copy_wheel_to_staging,
    remove_repository_transaction_folder,
)
from liberrpa.ComponentManagement.Domain.Repository._VersionEntry import build_repository_version_entry

import os
import uuid


def publish_component_wheel(
    manifestObj: Info_ProjectManifest_Component,
    wheelResult: Info_ComponentWheel_BuildResult,
) -> Info_Repository_PublishResult:
    pathRepository = get_repository_path()

    with repository_lock(repositoryPath=pathRepository, operation="publishComponent"):
        _, pathStaging = initialize_repository_structure(pathRepository)

        listWarning = recover_repository_transactions(pathRepository)
        dictIndex = load_repository_index(pathRepository, checkWheelPaths=True)
        dictComponent = dictIndex["components"].get(manifestObj.id)
        dictVersionEntry = build_repository_version_entry(
            manifestObj=manifestObj,
            wheelFile=wheelResult.wheelFile,
            sha256=wheelResult.sha256,
        )

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
            if is_file_invalid(pathExistingWheel):
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

                return Info_Repository_PublishResult(
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
        dictTransaction: DictRepository_Transaction_Publish = {
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

        dictWarning: DictComponentManagementWarning | None = remove_repository_transaction_folder(pathTransaction)
        if dictWarning is not None:
            listWarning.append(dictWarning)

        return Info_Repository_PublishResult(
            status="published",
            warnings=listWarning,
        )
