# FileName: _Resolver.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Version import get_installed_liberrpa_version
from liberrpa.ComponentManagement.Types._Manifest import (
    Info_ProjectManifest_Component,
    Info_ProjectManifest,
)
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_ComponentVersionEntry,
    DictRepository_Component,
    DictRepository_Index,
)
from liberrpa.ComponentManagement.Types._Components import (
    DictComponentsLock_Component,
    DictComponentsLock_File,
)
from liberrpa.ComponentManagement.Domain.Dependency._ComponentsLock import (
    build_components_lock,
)
from liberrpa.ComponentManagement.Domain.Repository._Index import (
    validate_component_id,
    find_equivalent_version,
)

from dataclasses import dataclass
from packaging.specifiers import SpecifierSet
from packaging.version import Version


@dataclass(frozen=True)
class _DependencyRequirement:
    source: str
    specifier: str


@dataclass(frozen=True)
class _SelectedComponent:
    packageName: str
    versionEntry: DictRepository_ComponentVersionEntry


@dataclass(frozen=True)
class _ResolutionChoice:
    componentId: str
    repositoryComponentDict: DictRepository_Component
    requirementList: list[_DependencyRequirement]
    candidateVersionList: list[DictRepository_ComponentVersionEntry]


@dataclass(frozen=True)
class _CandidateVersionResult:
    candidateVersionList: list[DictRepository_ComponentVersionEntry]
    incompatibleVersionList: list[DictRepository_ComponentVersionEntry]


@dataclass(frozen=True)
class _ResolutionContext:
    manifestObj: Info_ProjectManifest
    repositoryIndexDict: DictRepository_Index
    existingLockDict: DictComponentsLock_File | None
    updateComponentIdSet: set[str]
    installedLiberrpaVersion: Version


class _DependencyResolutionFailure(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _get_requirement_details(
    requirementList: list[_DependencyRequirement],
) -> list[dict[str, str]]:
    return [
        {
            "source": requirementObj.source,
            "specifier": requirementObj.specifier,
        }
        for requirementObj in requirementList
    ]


def _does_version_satisfy_requirements(
    version: str,
    requirementList: list[_DependencyRequirement],
) -> bool:
    versionObj = Version(version)
    return all(
        SpecifierSet(requirementObj.specifier).contains(versionObj, prereleases=True)
        for requirementObj in requirementList
    )


def _is_prerelease_allowed_by_requirements(
    requirementList: list[_DependencyRequirement],
) -> bool:
    return any(
        SpecifierSet(requirementObj.specifier).prereleases is True
        for requirementObj in requirementList
    )


def _build_locked_component(
    packageName: str,
    versionEntry: DictRepository_ComponentVersionEntry,
) -> DictComponentsLock_Component:
    return {
        "packageName": packageName,
        "displayName": versionEntry["displayName"],
        "version": versionEntry["version"],
        "wheelFileName": versionEntry["wheelFileName"],
        "sha256": versionEntry["sha256"],
        "requiresLiberrpa": versionEntry["requiresLiberrpa"],
        "componentDependencies": dict(versionEntry["componentDependencies"]),
    }


def _is_existing_locked_artifact(
    contextObj: _ResolutionContext,
    componentId: str,
    packageName: str,
    versionEntry: DictRepository_ComponentVersionEntry,
) -> bool:
    if contextObj.existingLockDict is None:
        return False

    dictLockedComponent = contextObj.existingLockDict["components"].get(componentId)
    if dictLockedComponent is None:
        return False

    return dictLockedComponent == _build_locked_component(packageName, versionEntry)


def _is_component_version_allowed_by_environment(
    contextObj: _ResolutionContext,
    componentId: str,
    packageName: str,
    versionEntry: DictRepository_ComponentVersionEntry,
) -> bool:
    if SpecifierSet(versionEntry["requiresLiberrpa"]).contains(
        contextObj.installedLiberrpaVersion
    ):
        return True

    # Existing incompatible artifacts may be retained by unrelated Add, Change Requirement, or Remove operations.
    # An explicit Update must select a compatible artifact.
    return (
        componentId not in contextObj.updateComponentIdSet
        and _is_existing_locked_artifact(
            contextObj,
            componentId,
            packageName,
            versionEntry,
        )
    )


def _get_candidate_version_list(
    contextObj: _ResolutionContext,
    componentId: str,
    componentDict: DictRepository_Component,
    requirementList: list[_DependencyRequirement],
    *,
    lockedVersion: str | None,
    preferLockedVersion: bool,
) -> _CandidateVersionResult:
    listMatchingVersionEntry = [
        dictVersionEntry
        for dictVersionEntry in componentDict["versions"]
        if _does_version_satisfy_requirements(
            dictVersionEntry["version"], requirementList
        )
    ]
    listAllowedVersion = [
        dictVersionEntry
        for dictVersionEntry in listMatchingVersionEntry
        if _is_component_version_allowed_by_environment(
            contextObj,
            componentId,
            componentDict["packageName"],
            dictVersionEntry,
        )
    ]
    listIncompatibleVersionEntry = [
        dictVersionEntry
        for dictVersionEntry in listMatchingVersionEntry
        if dictVersionEntry not in listAllowedVersion
    ]

    listStableVersionEntry = sorted(
        (
            dictVersionEntry
            for dictVersionEntry in listAllowedVersion
            if not Version(dictVersionEntry["version"]).is_prerelease
        ),
        key=lambda dictVersionEntry: Version(dictVersionEntry["version"]),
        reverse=True,
    )

    boolAllowPrerelease = _is_prerelease_allowed_by_requirements(requirementList)
    listPrereleaseVersion = (
        sorted(
            (
                dictVersionEntry
                for dictVersionEntry in listAllowedVersion
                if Version(dictVersionEntry["version"]).is_prerelease
            ),
            key=lambda dictVersionEntry: Version(dictVersionEntry["version"]),
            reverse=True,
        )
        if boolAllowPrerelease
        else []
    )

    listCandidate = [*listStableVersionEntry, *listPrereleaseVersion]

    if not preferLockedVersion or lockedVersion is None:
        return _CandidateVersionResult(
            candidateVersionList=listCandidate,
            incompatibleVersionList=listIncompatibleVersionEntry,
        )

    # Retaining an already locked prerelease is allowed. Selecting a new prerelease still requires an explicit prerelease specifier.
    dictLockedVersion = find_equivalent_version(componentDict, lockedVersion)
    if dictLockedVersion is None or not _does_version_satisfy_requirements(
        dictLockedVersion["version"], requirementList
    ):
        return _CandidateVersionResult(
            candidateVersionList=listCandidate,
            incompatibleVersionList=listIncompatibleVersionEntry,
        )

    if dictLockedVersion not in listAllowedVersion:
        return _CandidateVersionResult(
            candidateVersionList=listCandidate,
            incompatibleVersionList=listIncompatibleVersionEntry,
        )

    return _CandidateVersionResult(
        candidateVersionList=[
            dictLockedVersion,
            *(
                dictVersionEntry
                for dictVersionEntry in listCandidate
                if Version(dictVersionEntry["version"])
                != Version(dictLockedVersion["version"])
            ),
        ],
        incompatibleVersionList=listIncompatibleVersionEntry,
    )


def _validate_root_dependency(
    manifestObj: Info_ProjectManifest,
    requirementDict: dict[str, list[_DependencyRequirement]],
) -> None:
    if (
        not isinstance(manifestObj, Info_ProjectManifest_Component)
        or manifestObj.id not in requirementDict
    ):
        return

    raise _DependencyResolutionFailure(
        code="component_dependency_cycle",
        message="A resolved Component dependency refers back to the root Component.",
        details={
            "rootComponentId": manifestObj.id,
            "requirements": _get_requirement_details(requirementDict[manifestObj.id]),
        },
    )


def _validate_selected_versions(
    contextObj: _ResolutionContext,
    selectedComponentDict: dict[str, _SelectedComponent],
    requirementDict: dict[str, list[_DependencyRequirement]],
) -> None:
    for strComponentId, selectedComponentObj in selectedComponentDict.items():
        listRequirement = requirementDict.get(strComponentId)
        if listRequirement is None:
            raise _DependencyResolutionFailure(
                code="component_dependency_resolution_failed",
                message=f"Resolved Component {strComponentId} is no longer reachable from the Project.",
                details={"componentId": strComponentId},
            )

        if _does_version_satisfy_requirements(
            selectedComponentObj.versionEntry["version"], listRequirement
        ):
            if _is_component_version_allowed_by_environment(
                contextObj,
                strComponentId,
                selectedComponentObj.packageName,
                selectedComponentObj.versionEntry,
            ):
                continue

            raise _DependencyResolutionFailure(
                code="component_liberrpa_incompatible",
                message=(
                    f"Component {strComponentId} {selectedComponentObj.versionEntry['version']} is not compatible with installed liberrpa {contextObj.installedLiberrpaVersion}."
                ),
                details={
                    "componentId": strComponentId,
                    "packageName": selectedComponentObj.packageName,
                    "version": selectedComponentObj.versionEntry["version"],
                    "requiresLiberrpa": selectedComponentObj.versionEntry[
                        "requiresLiberrpa"
                    ],
                    "installedLiberrpaVersion": str(contextObj.installedLiberrpaVersion),
                },
            )

        raise _DependencyResolutionFailure(
            code="component_version_conflict",
            message=(
                f"Component {strComponentId} {selectedComponentObj.versionEntry['version']} does not satisfy all dependency requirements."
            ),
            details={
                "componentId": strComponentId,
                "selectedVersion": selectedComponentObj.versionEntry["version"],
                "requirements": _get_requirement_details(listRequirement),
            },
        )


def _validate_selected_dependency_cycle(
    selectedComponentDict: dict[str, _SelectedComponent],
) -> None:
    setVisited: set[str] = set()
    setVisiting: set[str] = set()
    listVisitPath: list[str] = []

    def visit_component(componentId: str) -> None:
        if componentId in setVisited:
            return

        if componentId in setVisiting:
            intCycleStart = listVisitPath.index(componentId)
            listCycle = [*listVisitPath[intCycleStart:], componentId]
            raise _DependencyResolutionFailure(
                code="component_dependency_cycle",
                message=f"Component dependency cycle detected: {' -> '.join(listCycle)}.",
                details={"componentCycle": listCycle},
            )

        setVisiting.add(componentId)
        listVisitPath.append(componentId)

        for strComponentId in selectedComponentDict[componentId].versionEntry[
            "componentDependencies"
        ]:
            if strComponentId in selectedComponentDict:
                visit_component(strComponentId)

        listVisitPath.pop()
        setVisiting.remove(componentId)
        setVisited.add(componentId)

    for strComponentId in sorted(selectedComponentDict):
        visit_component(strComponentId)


def _get_package_owner_dict(
    manifestObj: Info_ProjectManifest,
    selectedComponentDict: dict[str, _SelectedComponent],
) -> dict[str, str]:
    dictPackageNameOwner: dict[str, str] = {}

    if isinstance(manifestObj, Info_ProjectManifest_Component):
        dictPackageNameOwner[manifestObj.packageName.casefold()] = "root Component"

    for strComponentId, selectedComponentObj in selectedComponentDict.items():
        strPackageNameKey = selectedComponentObj.packageName.casefold()
        strExistingOwner = dictPackageNameOwner.get(strPackageNameKey)
        if strExistingOwner is not None:
            raise _DependencyResolutionFailure(
                code="component_package_conflict",
                message=f"Package name {selectedComponentObj.packageName!r} is used by more than one Component.",
                details={
                    "packageName": selectedComponentObj.packageName,
                    "existingOwner": strExistingOwner,
                    "conflictingOwner": f"Component {strComponentId}",
                },
            )

        dictPackageNameOwner[strPackageNameKey] = f"Component {strComponentId}"

    return dictPackageNameOwner


def _validate_candidate_package_name(
    componentId: str,
    packageName: str,
    packageNameOwnerDict: dict[str, str],
) -> None:
    strExistingOwner = packageNameOwnerDict.get(packageName.casefold())
    if strExistingOwner is None:
        return

    raise _DependencyResolutionFailure(
        code="component_package_conflict",
        message=f"Package name {packageName!r} is already used by {strExistingOwner}.",
        details={
            "componentId": componentId,
            "packageName": packageName,
            "existingOwner": strExistingOwner,
        },
    )


def _get_requirement_dict(
    manifestObj: Info_ProjectManifest,
    selectedComponentDict: dict[str, _SelectedComponent],
) -> dict[str, list[_DependencyRequirement]]:
    dictRequirement: dict[str, list[_DependencyRequirement]] = {}

    for strComponentId, strSpecifier in manifestObj.componentDependencies.items():
        dictRequirement.setdefault(strComponentId, []).append(
            _DependencyRequirement(
                source="Project",
                specifier=strSpecifier,
            )
        )

    for strComponentId, selectedComponentObj in selectedComponentDict.items():
        for strDependencyId, strSpecifier in selectedComponentObj.versionEntry[
            "componentDependencies"
        ].items():
            dictRequirement.setdefault(strDependencyId, []).append(
                _DependencyRequirement(
                    source=f"Component {strComponentId} {selectedComponentObj.versionEntry['version']}",
                    specifier=strSpecifier,
                )
            )

    for listRequirement in dictRequirement.values():
        listRequirement.sort(
            key=lambda requirementObj: (requirementObj.source, requirementObj.specifier)
        )

    return dictRequirement


def _resolve_selected_components(
    contextObj: _ResolutionContext,
    selectedComponentDict: dict[str, _SelectedComponent],
) -> dict[str, _SelectedComponent]:
    manifestObj = contextObj.manifestObj
    dictRequirement = _get_requirement_dict(manifestObj, selectedComponentDict)

    _validate_root_dependency(manifestObj, dictRequirement)
    _validate_selected_versions(contextObj, selectedComponentDict, dictRequirement)
    _validate_selected_dependency_cycle(selectedComponentDict)
    dictPackageNameOwner = _get_package_owner_dict(manifestObj, selectedComponentDict)

    listUnresolvedComponentId = sorted(set(dictRequirement) - set(selectedComponentDict))
    if not listUnresolvedComponentId:
        return selectedComponentDict

    listResolutionChoice: list[_ResolutionChoice] = []

    for strComponentId in listUnresolvedComponentId:
        dictRepositoryComponent = contextObj.repositoryIndexDict["components"].get(
            strComponentId
        )
        if dictRepositoryComponent is None:
            raise _DependencyResolutionFailure(
                code="component_not_found",
                message=f"Component {strComponentId} was not found in the Component Repository.",
                details={
                    "componentId": strComponentId,
                    "requirements": _get_requirement_details(
                        dictRequirement[strComponentId]
                    ),
                },
            )

        _validate_candidate_package_name(
            strComponentId,
            dictRepositoryComponent["packageName"],
            dictPackageNameOwner,
        )
        dictPackageNameOwner[dictRepositoryComponent["packageName"].casefold()] = (
            f"Component {strComponentId}"
        )

        strLockedVersion = (
            contextObj.existingLockDict["components"][strComponentId]["version"]
            if contextObj.existingLockDict is not None
            and strComponentId in contextObj.existingLockDict["components"]
            else None
        )
        candidateVersionResult = _get_candidate_version_list(
            contextObj,
            strComponentId,
            dictRepositoryComponent,
            dictRequirement[strComponentId],
            lockedVersion=strLockedVersion,
            preferLockedVersion=strComponentId not in contextObj.updateComponentIdSet,
        )
        listCandidateVersionEntry = candidateVersionResult.candidateVersionList

        if not listCandidateVersionEntry:
            if candidateVersionResult.incompatibleVersionList:
                raise _DependencyResolutionFailure(
                    code="component_liberrpa_incompatible",
                    message=(
                        f"No published version of Component {strComponentId} satisfies the dependency requirements and supports installed liberrpa {contextObj.installedLiberrpaVersion}."
                    ),
                    details={
                        "componentId": strComponentId,
                        "packageName": dictRepositoryComponent["packageName"],
                        "installedLiberrpaVersion": str(
                            contextObj.installedLiberrpaVersion
                        ),
                        "requirements": _get_requirement_details(
                            dictRequirement[strComponentId]
                        ),
                        "incompatibleVersions": [
                            {
                                "version": dictVersionEntry["version"],
                                "requiresLiberrpa": dictVersionEntry["requiresLiberrpa"],
                            }
                            for dictVersionEntry in candidateVersionResult.incompatibleVersionList
                        ],
                    },
                )

            raise _DependencyResolutionFailure(
                code="component_version_unavailable",
                message=f"No published version of Component {strComponentId} satisfies all dependency requirements.",
                details={
                    "componentId": strComponentId,
                    "packageName": dictRepositoryComponent["packageName"],
                    "requirements": _get_requirement_details(
                        dictRequirement[strComponentId]
                    ),
                    "availableVersions": [
                        dictVersionEntry["version"]
                        for dictVersionEntry in reversed(
                            dictRepositoryComponent["versions"]
                        )
                    ],
                },
            )

        listResolutionChoice.append(
            _ResolutionChoice(
                componentId=strComponentId,
                repositoryComponentDict=dictRepositoryComponent,
                requirementList=dictRequirement[strComponentId],
                candidateVersionList=listCandidateVersionEntry,
            )
        )

    resolutionChoiceObj = min(
        listResolutionChoice,
        key=lambda choiceObj: (
            len(choiceObj.candidateVersionList),
            choiceObj.componentId,
        ),
    )
    strSelectedComponentId = resolutionChoiceObj.componentId
    dictRepositoryComponent = resolutionChoiceObj.repositoryComponentDict
    listRequirement = resolutionChoiceObj.requirementList
    listCandidateVersionEntry = resolutionChoiceObj.candidateVersionList

    firstFailureObj: _DependencyResolutionFailure | None = None

    for dictVersionEntry in listCandidateVersionEntry:
        dictNextSelectedComponent = dict(selectedComponentDict)
        dictNextSelectedComponent[strSelectedComponentId] = _SelectedComponent(
            packageName=dictRepositoryComponent["packageName"],
            versionEntry=dictVersionEntry,
        )

        try:
            return _resolve_selected_components(
                contextObj,
                dictNextSelectedComponent,
            )
        except _DependencyResolutionFailure as e:
            if firstFailureObj is None:
                firstFailureObj = e

    assert firstFailureObj is not None
    if len(listCandidateVersionEntry) == 1:
        raise firstFailureObj

    raise _DependencyResolutionFailure(
        code="component_dependency_resolution_failed",
        message=f"No compatible dependency set could be resolved for Component {strSelectedComponentId}.",
        details={
            "componentId": strSelectedComponentId,
            "packageName": dictRepositoryComponent["packageName"],
            "requirements": _get_requirement_details(listRequirement),
            "attemptedVersions": [
                dictVersionEntry["version"]
                for dictVersionEntry in listCandidateVersionEntry
            ],
            "firstConflict": {
                "code": firstFailureObj.code,
                "message": firstFailureObj.message,
                "details": firstFailureObj.details,
            },
        },
    )


def resolve_project_dependencies(
    manifestObj: Info_ProjectManifest,
    repositoryIndexDict: DictRepository_Index,
    *,
    existingLockDict: DictComponentsLock_File | None = None,
    updateComponentIdSet: set[str] | None = None,
    # NOTE: The argument has not been used yet.
    installedLiberrpaVersion: Version | None = None,
) -> DictComponentsLock_File:
    """Resolve the complete exact Component closure for a normalized Project Manifest."""
    try:
        setUpdateComponentId = {
            validate_component_id(componentId, f"updateComponentIdSet.{componentId}")
            for componentId in (updateComponentIdSet or set())
        }
    except ValueError as e:
        raise ComponentManagementError(
            code="dependency_resolution_invalid_input",
            message="updateComponentIdSet contains an invalid Component ID.",
            details={"reason": str(e)},
        ) from e

    if setUpdateComponentId:
        if existingLockDict is None:
            raise ComponentManagementError(
                code="dependency_resolution_invalid_input",
                message="Updating Components requires an existing components.lock.json.",
            )

        listMissingUpdateComponentId = sorted(
            setUpdateComponentId - set(existingLockDict["components"])
        )
        if listMissingUpdateComponentId:
            raise ComponentManagementError(
                code="dependency_resolution_invalid_input",
                message="The requested Update contains Components that are not present in components.lock.json.",
                details={"missingComponentIds": listMissingUpdateComponentId},
            )

    if installedLiberrpaVersion is None:
        try:
            installedLiberrpaVersion = get_installed_liberrpa_version()
        except ValueError as e:
            raise ComponentManagementError(
                code="liberrpa_version_unavailable",
                message="The installed liberrpa version could not be determined for Component dependency resolution.",
                details={"reason": str(e)},
            ) from e

    try:
        contextObj = _ResolutionContext(
            manifestObj=manifestObj,
            repositoryIndexDict=repositoryIndexDict,
            existingLockDict=existingLockDict,
            updateComponentIdSet=setUpdateComponentId,
            installedLiberrpaVersion=installedLiberrpaVersion,
        )
        dictSelectedComponent = _resolve_selected_components(contextObj, {})
    except _DependencyResolutionFailure as e:
        raise ComponentManagementError(
            code=e.code,
            message=e.message,
            details=e.details,
        ) from e
    except ValueError as e:
        raise ComponentManagementError(
            code="dependency_resolution_invalid_input",
            message="Dependency resolution received invalid Component data.",
            details={"reason": str(e)},
        ) from e

    listUnresolvedUpdateComponentId = sorted(
        setUpdateComponentId - set(dictSelectedComponent)
    )
    if listUnresolvedUpdateComponentId:
        raise ComponentManagementError(
            code="dependency_resolution_invalid_input",
            message="The requested Update contains Components that are no longer required by the Project.",
            details={"unreachableComponentIds": listUnresolvedUpdateComponentId},
        )

    dictLockedComponent = {
        strComponentId: _build_locked_component(
            selectedComponentObj.packageName,
            selectedComponentObj.versionEntry,
        )
        for strComponentId, selectedComponentObj in sorted(dictSelectedComponent.items())
    }

    try:
        return build_components_lock(manifestObj, dictLockedComponent)
    except ValueError as e:
        raise ComponentManagementError(
            code="component_dependency_resolution_failed",
            message="The resolved Component dependency set is invalid.",
            details={"reason": str(e)},
        ) from e
