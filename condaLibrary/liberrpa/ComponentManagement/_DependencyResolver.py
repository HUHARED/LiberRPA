# FileName: _DependencyResolver.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._TypedValue import (
    ComponentManifest,
    ProjectManifest,
    DictRepositoryComponentVersion,
    DictRepositoryComponent,
    DictRepositoryIndex,
    DictLockedComponent,
    DictComponentsLockFile,
)
from liberrpa.ComponentManagement._ComponentsLock import build_components_lock
from liberrpa.ComponentManagement._RepositoryIndex import find_equivalent_version, normalize_component_id

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
    versionEntry: DictRepositoryComponentVersion


@dataclass(frozen=True)
class _ResolutionChoice:
    componentId: str
    repositoryComponent: DictRepositoryComponent
    requirementList: list[_DependencyRequirement]
    candidateVersionList: list[DictRepositoryComponentVersion]


@dataclass(frozen=True)
class _ResolutionContext:
    manifestObj: ProjectManifest
    repositoryIndex: DictRepositoryIndex
    existingLock: DictComponentsLockFile | None
    updateComponentIdSet: set[str]


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


def _version_satisfies_requirements(
    version: str,
    requirementList: list[_DependencyRequirement],
) -> bool:
    versionObj = Version(version)
    return all(
        SpecifierSet(requirementObj.specifier).contains(versionObj, prereleases=True)
        for requirementObj in requirementList
    )


def _requirements_allow_prerelease(requirementList: list[_DependencyRequirement]) -> bool:
    return any(SpecifierSet(requirementObj.specifier).prereleases is True for requirementObj in requirementList)


def _get_candidate_version_list(
    componentDict: DictRepositoryComponent,
    requirementList: list[_DependencyRequirement],
    *,
    lockedVersion: str | None,
    preferLockedVersion: bool,
) -> list[DictRepositoryComponentVersion]:
    listMatchingVersion = [
        dictVersionEntry
        for dictVersionEntry in componentDict["versions"]
        if _version_satisfies_requirements(dictVersionEntry["version"], requirementList)
    ]

    listStableVersion = sorted(
        (
            dictVersionEntry
            for dictVersionEntry in listMatchingVersion
            if not Version(dictVersionEntry["version"]).is_prerelease
        ),
        key=lambda dictVersionEntry: Version(dictVersionEntry["version"]),
        reverse=True,
    )

    boolAllowPrerelease = _requirements_allow_prerelease(requirementList)
    listPrereleaseVersion = (
        sorted(
            (
                dictVersionEntry
                for dictVersionEntry in listMatchingVersion
                if Version(dictVersionEntry["version"]).is_prerelease
            ),
            key=lambda dictVersionEntry: Version(dictVersionEntry["version"]),
            reverse=True,
        )
        if boolAllowPrerelease
        else []
    )

    listCandidate = [*listStableVersion, *listPrereleaseVersion]

    if not preferLockedVersion or lockedVersion is None:
        return listCandidate

    # Retaining an already locked prerelease is allowed. Selecting a new prerelease still requires an explicit prerelease specifier.
    dictLockedVersion = find_equivalent_version(componentDict, lockedVersion)
    if dictLockedVersion is None or not _version_satisfies_requirements(
        dictLockedVersion["version"],
        requirementList,
    ):
        return listCandidate

    return [
        dictLockedVersion,
        *(
            dictVersionEntry
            for dictVersionEntry in listCandidate
            if Version(dictVersionEntry["version"]) != Version(dictLockedVersion["version"])
        ),
    ]


def _validate_root_dependency(
    manifestObj: ProjectManifest,
    requirementDict: dict[str, list[_DependencyRequirement]],
) -> None:
    if not isinstance(manifestObj, ComponentManifest) or manifestObj.id not in requirementDict:
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
    selectedComponentDict: dict[str, _SelectedComponent],
    requirementDict: dict[str, list[_DependencyRequirement]],
) -> None:
    for strComponentId, selectedComponent in selectedComponentDict.items():
        listRequirement = requirementDict.get(strComponentId)
        if listRequirement is None:
            raise _DependencyResolutionFailure(
                code="component_dependency_resolution_failed",
                message=f"Resolved Component {strComponentId} is no longer reachable from the Project.",
                details={"componentId": strComponentId},
            )

        if _version_satisfies_requirements(selectedComponent.versionEntry["version"], listRequirement):
            continue

        raise _DependencyResolutionFailure(
            code="component_version_conflict",
            message=(
                f"Component {strComponentId} {selectedComponent.versionEntry['version']} does not satisfy all dependency requirements."
            ),
            details={
                "componentId": strComponentId,
                "selectedVersion": selectedComponent.versionEntry["version"],
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

        for strDependencyId in selectedComponentDict[componentId].versionEntry["componentDependencies"]:
            if strDependencyId in selectedComponentDict:
                visit_component(strDependencyId)

        listVisitPath.pop()
        setVisiting.remove(componentId)
        setVisited.add(componentId)

    for strComponentId in sorted(selectedComponentDict):
        visit_component(strComponentId)


def _get_package_owner_dict(
    manifestObj: ProjectManifest,
    selectedComponentDict: dict[str, _SelectedComponent],
) -> dict[str, str]:
    dictPackageOwner: dict[str, str] = {}

    if isinstance(manifestObj, ComponentManifest):
        dictPackageOwner[manifestObj.packageName.casefold()] = "root Component"

    for strComponentId, selectedComponent in selectedComponentDict.items():
        strPackageKey = selectedComponent.packageName.casefold()
        strExistingOwner = dictPackageOwner.get(strPackageKey)
        if strExistingOwner is not None:
            raise _DependencyResolutionFailure(
                code="component_package_conflict",
                message=f"Package name {selectedComponent.packageName!r} is used by more than one Component.",
                details={
                    "packageName": selectedComponent.packageName,
                    "existingOwner": strExistingOwner,
                    "conflictingOwner": f"Component {strComponentId}",
                },
            )

        dictPackageOwner[strPackageKey] = f"Component {strComponentId}"

    return dictPackageOwner


def _validate_candidate_package_name(
    componentId: str,
    packageName: str,
    packageOwnerDict: dict[str, str],
) -> None:
    strExistingOwner = packageOwnerDict.get(packageName.casefold())
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


def _build_locked_component(
    packageName: str,
    versionEntry: DictRepositoryComponentVersion,
) -> DictLockedComponent:
    return {
        "manifestSchemaVersion": versionEntry["manifestSchemaVersion"],
        "packageName": packageName,
        "displayName": versionEntry["displayName"],
        "version": versionEntry["version"],
        "wheelFile": versionEntry["wheelFile"],
        "sha256": versionEntry["sha256"],
        "requiresLiberrpa": versionEntry["requiresLiberrpa"],
        "componentDependencies": dict(versionEntry["componentDependencies"]),
    }


def _get_requirement_dict(
    manifestObj: ProjectManifest,
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

    for strComponentId, selectedComponent in selectedComponentDict.items():
        for strDependencyId, strSpecifier in selectedComponent.versionEntry["componentDependencies"].items():
            dictRequirement.setdefault(strDependencyId, []).append(
                _DependencyRequirement(
                    source=f"Component {strComponentId} {selectedComponent.versionEntry['version']}",
                    specifier=strSpecifier,
                )
            )

    for listRequirement in dictRequirement.values():
        listRequirement.sort(key=lambda requirementObj: (requirementObj.source, requirementObj.specifier))

    return dictRequirement


def _resolve_selected_components(
    contextObj: _ResolutionContext,
    selectedComponentDict: dict[str, _SelectedComponent],
) -> dict[str, _SelectedComponent]:
    manifestObj = contextObj.manifestObj
    dictRequirement = _get_requirement_dict(manifestObj, selectedComponentDict)
    _validate_root_dependency(manifestObj, dictRequirement)
    _validate_selected_versions(selectedComponentDict, dictRequirement)
    _validate_selected_dependency_cycle(selectedComponentDict)
    dictPackageOwner = _get_package_owner_dict(manifestObj, selectedComponentDict)

    listUnresolvedComponentId = sorted(set(dictRequirement) - set(selectedComponentDict))
    if not listUnresolvedComponentId:
        return selectedComponentDict

    listResolutionChoice: list[_ResolutionChoice] = []

    for strComponentId in listUnresolvedComponentId:
        dictRepositoryComponent = contextObj.repositoryIndex["components"].get(strComponentId)
        if dictRepositoryComponent is None:
            raise _DependencyResolutionFailure(
                code="component_not_found",
                message=f"Component {strComponentId} was not found in the Component Repository.",
                details={
                    "componentId": strComponentId,
                    "requirements": _get_requirement_details(dictRequirement[strComponentId]),
                },
            )

        _validate_candidate_package_name(
            strComponentId,
            dictRepositoryComponent["packageName"],
            dictPackageOwner,
        )
        dictPackageOwner[dictRepositoryComponent["packageName"].casefold()] = f"Component {strComponentId}"

        strLockedVersion = (
            contextObj.existingLock["components"][strComponentId]["version"]
            if contextObj.existingLock is not None and strComponentId in contextObj.existingLock["components"]
            else None
        )
        listCandidateVersion = _get_candidate_version_list(
            dictRepositoryComponent,
            dictRequirement[strComponentId],
            lockedVersion=strLockedVersion,
            preferLockedVersion=strComponentId not in contextObj.updateComponentIdSet,
        )

        if not listCandidateVersion:
            raise _DependencyResolutionFailure(
                code="component_version_unavailable",
                message=f"No published version of Component {strComponentId} satisfies all dependency requirements.",
                details={
                    "componentId": strComponentId,
                    "packageName": dictRepositoryComponent["packageName"],
                    "requirements": _get_requirement_details(dictRequirement[strComponentId]),
                    "availableVersions": [
                        dictVersionEntry["version"]
                        for dictVersionEntry in reversed(dictRepositoryComponent["versions"])
                    ],
                },
            )

        listResolutionChoice.append(
            _ResolutionChoice(
                componentId=strComponentId,
                repositoryComponent=dictRepositoryComponent,
                requirementList=dictRequirement[strComponentId],
                candidateVersionList=listCandidateVersion,
            )
        )

    resolutionChoiceObj = min(
        listResolutionChoice,
        key=lambda choiceObj: (len(choiceObj.candidateVersionList), choiceObj.componentId),
    )
    strSelectedComponentId = resolutionChoiceObj.componentId
    dictRepositoryComponent = resolutionChoiceObj.repositoryComponent
    listRequirement = resolutionChoiceObj.requirementList
    listCandidateVersion = resolutionChoiceObj.candidateVersionList

    firstFailureObj: _DependencyResolutionFailure | None = None

    for dictVersionEntry in listCandidateVersion:
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
    if len(listCandidateVersion) == 1:
        raise firstFailureObj

    raise _DependencyResolutionFailure(
        code="component_dependency_resolution_failed",
        message=f"No compatible dependency set could be resolved for Component {strSelectedComponentId}.",
        details={
            "componentId": strSelectedComponentId,
            "packageName": dictRepositoryComponent["packageName"],
            "requirements": _get_requirement_details(listRequirement),
            "attemptedVersions": [dictVersionEntry["version"] for dictVersionEntry in listCandidateVersion],
            "firstConflict": {
                "code": firstFailureObj.code,
                "message": firstFailureObj.message,
                "details": firstFailureObj.details,
            },
        },
    )


def resolve_project_dependencies(
    manifestObj: ProjectManifest,
    repositoryIndex: DictRepositoryIndex,
    *,
    existingLock: DictComponentsLockFile | None = None,
    updateComponentIdSet: set[str] | None = None,
) -> DictComponentsLockFile:
    """Resolve the complete exact Component closure for a normalized Project Manifest."""
    try:
        setUpdateComponentId = {
            normalize_component_id(componentId, f"updateComponentIdSet.{componentId}")
            for componentId in (updateComponentIdSet or set())
        }
    except ValueError as e:
        raise ComponentManagementError(
            code="dependency_resolution_invalid_input",
            message="updateComponentIdSet contains an invalid Component ID.",
            details={"reason": str(e)},
        ) from e

    if setUpdateComponentId:
        if existingLock is None:
            raise ComponentManagementError(
                code="dependency_resolution_invalid_input",
                message="Updating Components requires an existing components.lock.json.",
            )

        listMissingUpdateComponentId = sorted(setUpdateComponentId - set(existingLock["components"]))
        if listMissingUpdateComponentId:
            raise ComponentManagementError(
                code="dependency_resolution_invalid_input",
                message="The requested Update contains Components that are not present in components.lock.json.",
                details={"missingComponentIds": listMissingUpdateComponentId},
            )

    try:
        contextObj = _ResolutionContext(
            manifestObj=manifestObj,
            repositoryIndex=repositoryIndex,
            existingLock=existingLock,
            updateComponentIdSet=setUpdateComponentId,
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

    listUnresolvedUpdateComponentId = sorted(setUpdateComponentId - set(dictSelectedComponent))
    if listUnresolvedUpdateComponentId:
        raise ComponentManagementError(
            code="dependency_resolution_invalid_input",
            message="The requested Update contains Components that are no longer required by the Project.",
            details={"unreachableComponentIds": listUnresolvedUpdateComponentId},
        )

    dictLockedComponent = {
        strComponentId: _build_locked_component(
            selectedComponent.packageName,
            selectedComponent.versionEntry,
        )
        for strComponentId, selectedComponent in sorted(dictSelectedComponent.items())
    }

    try:
        return build_components_lock(manifestObj, dictLockedComponent)
    except ValueError as e:
        raise ComponentManagementError(
            code="component_dependency_resolution_failed",
            message="The resolved Component dependency set is invalid.",
            details={"reason": str(e)},
        ) from e
