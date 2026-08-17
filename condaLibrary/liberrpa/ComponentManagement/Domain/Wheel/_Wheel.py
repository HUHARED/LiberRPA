# FileName: _Wheel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._File import parse_json, serialize_json
from liberrpa.ComponentManagement.Common._Hash import (
    calculate_file_sha256,
    calculate_record_hash,
)
from liberrpa.ComponentManagement.Common._Record import (
    validate_archive_path,
    validate_record,
)
from liberrpa.ComponentManagement.Common._WheelName import (
    STR_COMPONENT_WHEEL_TAG,
    TAG_COMPONENT_WHEEL,
    get_component_wheel_names,
)
from liberrpa.ComponentManagement.Common._Validation import (
    validate_exact_keys,
    is_file_invalid,
)
from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Snippet import (
    DictSnippet_Imports,
    DictSnippet_Normalized,
    DictSnippet_CatalogFile,
)
from liberrpa.ComponentManagement.Types._Wheel import (
    Info_ComponentWheel_BuildResult,
    Info_ComponentWheel,
)
from liberrpa.ComponentManagement.Domain.Manifest._Manifest import (
    parse_component_manifest,
    build_project_manifest_dict,
)


from csv import writer
from email import policy
from email.message import Message
from email.parser import BytesParser
from io import StringIO
from pathlib import Path, PurePosixPath
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from zipfile import (
    ZIP_STORED,  # Avoid compressor-version differences so identical inputs produce identical Wheel bytes and SHA-256 values.
    BadZipFile,
    ZipFile,
    ZipInfo,
)
import keyword
import os
import re
import stat
import uuid


_TUPLE_ZIP_TIMESTAMP = (
    1984,
    4,
    4,
    0,
    0,
    0,
)  # A fixed timestamp for keeping zip binary result same.
_INT_ZIP_FILE_MODE = (stat.S_IFREG | 0o644) << 16  # Owner can edit, others can read.

_SET_IGNORED_FILE_SUFFIX = {
    ".pyc",
    ".pyo",
}

# LiberRPA runs only on Windows, so Component packages may include user-managed script resources such as .bat, .cmd, and .ps1 files. Native libraries, Python extension modules, and standalone executable binaries remain unsupported to keep Component packaging and recovery predictable.
_SET_FORBIDDEN_FILE_SUFFIX = {
    # ".bat",
    # ".cmd",
    # ".ps1",
    ".dll",
    ".dylib",
    ".exe",
    ".pyd",
    ".so",
}


def _get_package_archive_entries(
    packageFolderPath: Path,
    packageName: str,
) -> dict[str, bytes]:
    """Determine which files can be packaged."""
    dictEntry: dict[str, bytes] = {}
    dictCaseInsensitivePath: dict[str, str] = {}

    def scan_package_folder(folderPath: Path) -> None:
        try:
            with os.scandir(folderPath) as folderIterator:
                listSourceEntry = sorted(
                    folderIterator, key=lambda entryObj: entryObj.name
                )
        except OSError as e:
            raise ComponentManagementError(
                code="io_error",
                message=f"Failed to scan Component package folder: {folderPath}",
            ) from e

        for entryObj in listSourceEntry:
            pathSourceEntry = Path(entryObj.path)
            pathRelativeSourceEntry = pathSourceEntry.relative_to(packageFolderPath)

            try:
                if entryObj.is_symlink() or entryObj.is_junction():
                    raise ComponentManagementError(
                        code="unsupported_component_file",
                        message=(
                            f"Component package cannot contain symbolic links or junctions: {pathSourceEntry}"
                        ),
                        details={"relativeFilePath": pathRelativeSourceEntry.as_posix()},
                    )

                if entryObj.is_dir(follow_symlinks=False):
                    if entryObj.name != "__pycache__":
                        scan_package_folder(pathSourceEntry)
                    continue

                if not entryObj.is_file(follow_symlinks=False):
                    raise ComponentManagementError(
                        code="unsupported_component_file",
                        message=f"Unsupported Component package entry: {pathSourceEntry}",
                        details={"relativeFilePath": pathRelativeSourceEntry.as_posix()},
                    )
            except OSError as e:
                raise ComponentManagementError(
                    code="io_error",
                    message=f"Failed to inspect Component package entry: {pathSourceEntry}",
                ) from e

            strSuffix = pathSourceEntry.suffix.casefold()
            if strSuffix in _SET_IGNORED_FILE_SUFFIX:
                continue
            if strSuffix in _SET_FORBIDDEN_FILE_SUFFIX:
                raise ComponentManagementError(
                    code="unsupported_component_file",
                    message=f"Unsupported Component package file type: {pathSourceEntry}",
                    details={"relativeFilePath": pathRelativeSourceEntry.as_posix()},
                )

            strArchivePath = PurePosixPath(
                packageName, *pathRelativeSourceEntry.parts
            ).as_posix()
            try:
                validate_archive_path(strArchivePath)
            except ValueError as e:
                raise ComponentManagementError(
                    code="component_source_invalid",
                    message="Component package contains a path that is invalid on Windows.",
                    details={
                        "relativeFilePath": pathRelativeSourceEntry.as_posix(),
                        "reason": str(e),
                    },
                ) from e

            strCaseInsensitivePath = strArchivePath.casefold()
            strExistingPath = dictCaseInsensitivePath.get(strCaseInsensitivePath)
            if strExistingPath is not None:
                raise ComponentManagementError(
                    code="component_source_invalid",
                    message="Component package contains paths that conflict on Windows.",
                    details={"paths": [strExistingPath, strArchivePath]},
                )
            dictCaseInsensitivePath[strCaseInsensitivePath] = strArchivePath

            try:
                dictEntry[strArchivePath] = pathSourceEntry.read_bytes()
            except OSError as e:
                raise ComponentManagementError(
                    code="io_error",
                    message=f"Failed to read Component package file: {pathSourceEntry}",
                ) from e

    scan_package_folder(packageFolderPath)
    return dictEntry


def _get_manifest_metadata_bytes(manifestObj: Info_ProjectManifest_Component) -> bytes:
    strMetadata = (
        # Core Metadata 2.4 is required because License-File was introduced in 2.4.
        "Metadata-Version: 2.4\n"
        f"Name: {manifestObj.packageName}\n"
        f"Version: {manifestObj.version}\n"
        # License-File: LICENSE == <dist-info>/licenses/LICENSE
        "License-File: LICENSE\n"
        "\n"
    )
    return strMetadata.encode()


def _get_wheel_metadata_bytes() -> bytes:
    return (
        # LiberRPA Component Wheels currently follow Wheel specification 1.0.
        f"Wheel-Version: 1.0\nGenerator: LiberRPA ComponentManagement\nRoot-Is-Purelib: true\nTag: {STR_COMPONENT_WHEEL_TAG}\n\n"
    ).encode()


def _get_record_bytes(
    archiveEntryDict: dict[str, bytes],
    recordPath: str,
) -> bytes:
    strBuffer = StringIO(newline="")
    csvWriter = writer(strBuffer, lineterminator="\n")

    for strArchivePath in sorted(archiveEntryDict):
        value = archiveEntryDict[strArchivePath]
        csvWriter.writerow([
            strArchivePath,
            calculate_record_hash(value),
            str(len(value)),
        ])

    csvWriter.writerow([recordPath, "", ""])
    return strBuffer.getvalue().encode()


def _create_zip_info(archivePath: str) -> ZipInfo:
    infoObj = ZipInfo(filename=archivePath, date_time=_TUPLE_ZIP_TIMESTAMP)
    infoObj.compress_type = ZIP_STORED
    infoObj.create_system = 3
    infoObj.external_attr = _INT_ZIP_FILE_MODE
    return infoObj


def _write_wheel_file(
    wheelFilePath: Path,
    archiveEntryDict: dict[str, bytes],
    recordPath: str,
) -> None:
    # Keep the temporary name independent of the final name so the UUID suffix cannot make a valid Windows filename exceed the entry name limit.
    pathTempWheelFile = wheelFilePath.parent / f".liberrpa-wheel-{uuid.uuid4()}.tmp"

    try:
        with ZipFile(pathTempWheelFile, mode="x", compression=ZIP_STORED) as wheelObj:
            for strArchivePath in sorted(archiveEntryDict):
                wheelObj.writestr(
                    _create_zip_info(strArchivePath),
                    archiveEntryDict[strArchivePath],
                )

            wheelObj.writestr(
                _create_zip_info(recordPath),
                _get_record_bytes(
                    archiveEntryDict=archiveEntryDict, recordPath=recordPath
                ),
            )

        os.replace(pathTempWheelFile, wheelFilePath)
    except (OSError, BadZipFile) as e:
        raise ComponentManagementError(
            code="wheel_build_failed",
            message=f"Failed to build Component Wheel: {wheelFilePath}",
        ) from e
    finally:
        pathTempWheelFile.unlink(missing_ok=True)


def build_component_wheel(
    projectPath: Path,
    packageFolderPath: Path,
    buildFolderPath: Path,
    manifestObj: Info_ProjectManifest_Component,
    snippetCatalog: DictSnippet_CatalogFile,
) -> Info_ComponentWheel_BuildResult:
    pathLicenseFile = projectPath / "LICENSE"
    if is_file_invalid(pathLicenseFile):
        raise ComponentManagementError(
            code="component_source_invalid",
            message=f"Component Project LICENSE file was not found or is invalid: {pathLicenseFile}",
        )

    strDistInfoFolder, strWheelFileName = get_component_wheel_names(
        manifestObj.packageName,
        manifestObj.version,
    )
    pathWheelFile = buildFolderPath / strWheelFileName

    try:
        bytesLicenseFile = pathLicenseFile.read_bytes()
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to read Component Project LICENSE file: {pathLicenseFile}",
        ) from e

    dictArchiveEntry = _get_package_archive_entries(
        packageFolderPath=packageFolderPath,
        packageName=manifestObj.packageName,
    )

    dictPublishedManifest = build_project_manifest_dict(manifestObj)
    strDistInfoPrefix = f"{strDistInfoFolder}/"
    dictArchiveEntry.update({
        f"{strDistInfoPrefix}METADATA": _get_manifest_metadata_bytes(manifestObj),
        f"{strDistInfoPrefix}WHEEL": _get_wheel_metadata_bytes(),
        f"{strDistInfoPrefix}licenses/LICENSE": bytesLicenseFile,
        f"{strDistInfoPrefix}component.json": serialize_json(
            dictPublishedManifest
        ).encode(),
        f"{strDistInfoPrefix}snippets_catalog.json": serialize_json(
            snippetCatalog
        ).encode(),
    })

    strRecordPath = f"{strDistInfoPrefix}RECORD"

    _write_wheel_file(
        wheelFilePath=pathWheelFile,
        archiveEntryDict=dictArchiveEntry,
        recordPath=strRecordPath,
    )
    strSha256 = _validate_component_wheel(
        wheelFilePath=pathWheelFile,
        manifestObj=manifestObj,
        snippetCatalogDict=snippetCatalog,
    )

    return Info_ComponentWheel_BuildResult(
        wheelFilePath=pathWheelFile,
        wheelFileName=strWheelFileName,
        sha256=strSha256,
    )


def _read_metadata(value: bytes, fileName: str) -> Message:
    metadataObj = BytesParser(
        policy=policy.compat32,
    ).parsebytes(
        value,
        headersonly=True,
    )

    if metadataObj.defects:
        raise ValueError(
            f"Invalid metadata headers in {fileName}: {metadataObj.defects!r}."
        )

    return metadataObj


_SET_KEYS_SNIPPET_CATALOG = {
    "schemaVersion",
    "categoryOrder",
    "categoryIcons",
    "importSources",
    "snippets",
}
_SET_KEYS_IMPORT_SOURCE_CONFIG = {"order", "aliasMode"}
_REGEX_PRODUCT_ICON_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SET_KEYS_NORMALIZED_SNIPPET = {
    "category",
    "label",
    "prefix",
    "body",
    "description",
    "imports",
    "insertionMode",
}


def _validate_identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError(f"{field} must be a valid non-keyword Python identifier.")

    return value


def _validate_single_line_string(value: object, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field} must be a non-empty string.")

    if "\r" in value or "\n" in value:
        raise ValueError(f"{field} must be a single line.")

    return value


def _validate_product_icon_id(value: object, field: str) -> str:
    if not isinstance(value, str) or _REGEX_PRODUCT_ICON_ID.fullmatch(value) is None:
        raise ValueError(
            f"{field} must be a lower-case VS Code Product Icon ID, such as 'watch' or 'symbol-method'."
        )

    return value


def _validate_catalog_imports(
    value: object,
    field: str,
    *,
    packageName: str,
    publicModuleSet: set[str],
) -> DictSnippet_Imports:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    dictResult: DictSnippet_Imports = {}

    for importSource, importNameValue in value.items():
        if not isinstance(importSource, str) or importSource == "":
            raise ValueError(f"{field} contains an invalid import source.")

        if not isinstance(importNameValue, list) or not importNameValue:
            raise ValueError(f"{field}.{importSource} must be a non-empty array.")

        listImportName: list[str] = []
        setImportName: set[str] = set()

        for intIndex, importName in enumerate(importNameValue):
            strImportName = _validate_identifier(
                importName,
                f"{field}.{importSource}[{intIndex}]",
            )

            if strImportName in setImportName:
                raise ValueError(
                    f"{field}.{importSource} contains duplicate import name {strImportName!r}."
                )

            if importSource == packageName and strImportName not in publicModuleSet:
                raise ValueError(
                    f"{field}.{importSource} contains unknown public Module {strImportName!r}."
                )

            setImportName.add(strImportName)
            listImportName.append(strImportName)

        dictResult[importSource] = listImportName

    return dictResult


def _validate_snippet_catalog(
    value: object,
    manifestObj: Info_ProjectManifest_Component,
) -> DictSnippet_CatalogFile:
    if not isinstance(value, dict):
        raise ValueError("snippets_catalog.json root value must be an object.")

    validate_exact_keys(value, _SET_KEYS_SNIPPET_CATALOG, "snippets_catalog.json")

    schemaVersion = value.get("schemaVersion")
    if type(schemaVersion) is not int or schemaVersion != 1:
        raise ValueError("snippets_catalog.json schemaVersion must be 1.")

    # Validate "importSources"
    importSourcesValue = value.get("importSources")
    if not isinstance(importSourcesValue, dict):
        raise ValueError("snippets_catalog.json importSources must be an object.")
    if set(importSourcesValue) != {manifestObj.packageName}:
        raise ValueError(
            "A Component snippets catalog must define exactly its own packageName as the import source."
        )

    sourceConfigValue = importSourcesValue[manifestObj.packageName]
    if not isinstance(sourceConfigValue, dict):
        raise ValueError(f"importSources.{manifestObj.packageName} must be an object.")
    validate_exact_keys(
        sourceConfigValue,
        _SET_KEYS_IMPORT_SOURCE_CONFIG,
        f"importSources.{manifestObj.packageName}",
    )
    if sourceConfigValue.get("aliasMode") != "source_module":
        raise ValueError(
            f"importSources.{manifestObj.packageName}.aliasMode must be 'source_module'."
        )

    moduleOrderValue = sourceConfigValue.get("order")
    if not isinstance(moduleOrderValue, list):
        raise ValueError(
            f"importSources.{manifestObj.packageName}.order must be an array."
        )
    listModuleOrder: list[str] = []
    setModule: set[str] = set()
    for intIndex, moduleName in enumerate(moduleOrderValue):
        strModuleName = _validate_identifier(
            moduleName,
            f"importSources.{manifestObj.packageName}.order[{intIndex}]",
        )
        if strModuleName in setModule:
            raise ValueError(
                f"importSources.{manifestObj.packageName}.order contains duplicate Module {strModuleName!r}."
            )
        setModule.add(strModuleName)
        listModuleOrder.append(strModuleName)

    # Validate "categoryOrder"
    categoryOrderValue = value.get("categoryOrder")
    if not isinstance(categoryOrderValue, list):
        raise ValueError("snippets_catalog.json categoryOrder must be an array.")
    listCategoryOrder: list[str] = []
    setCategory: set[str] = set()
    strCategoryPrefix = f"{manifestObj.packageName}_"
    for intIndex, category in enumerate(categoryOrderValue):
        if not isinstance(category, str) or not category.startswith(strCategoryPrefix):
            raise ValueError(
                f"categoryOrder[{intIndex}] must use {manifestObj.packageName}_ModuleName."
            )
        strModuleName = category[len(strCategoryPrefix) :]
        if strModuleName not in setModule:
            raise ValueError(
                f"categoryOrder[{intIndex}] refers to an unknown public Module."
            )
        if category in setCategory:
            raise ValueError(f"categoryOrder contains duplicate category {category!r}.")

        setCategory.add(category)
        listCategoryOrder.append(category)

    # Validate "categoryIcons"
    categoryIconsValue = value.get("categoryIcons")
    if not isinstance(categoryIconsValue, dict):
        raise ValueError("snippets_catalog.json categoryIcons must be an object.")
    if list(categoryIconsValue) != listCategoryOrder:
        raise ValueError(
            "categoryIcons must contain exactly the categoryOrder keys in the same order."
        )

    dictCategoryIcon = {
        category: _validate_product_icon_id(
            categoryIconsValue[category],
            f"categoryIcons.{category}",
        )
        for category in listCategoryOrder
    }

    # Validate "snippets"
    snippetsValue = value.get("snippets")
    if not isinstance(snippetsValue, dict):
        raise ValueError("snippets_catalog.json snippets must be an object.")

    dictLabelOwner: dict[tuple[str, str], str] = {}
    dictPrefixOwner: dict[str, str] = {}
    setUsedCategory: set[str] = set()
    dictSnippet: dict[str, DictSnippet_Normalized] = {}

    for snippetKey, snippetValue in snippetsValue.items():
        if not isinstance(snippetKey, str):
            raise ValueError("Every Snippet key must be a string.")

        strCategory, strSeparator, strSnippetName = snippetKey.partition(".")
        if (
            strSeparator == ""
            or "." in strSnippetName
            or strCategory not in setCategory
            or not strSnippetName.isidentifier()
            or keyword.iskeyword(strSnippetName)
        ):
            raise ValueError(f"Invalid Component Snippet key: {snippetKey!r}.")

        if not isinstance(snippetValue, dict):
            raise ValueError(f"snippets.{snippetKey} must be an object.")

        validate_exact_keys(
            snippetValue,
            _SET_KEYS_NORMALIZED_SNIPPET,
            f"snippets.{snippetKey}",
        )

        if snippetValue.get("category") != strCategory:
            raise ValueError(f"snippets.{snippetKey}.category does not match its key.")

        strLabel = _validate_single_line_string(
            snippetValue.get("label"),
            f"snippets.{snippetKey}.label",
        )
        tupleLabel = (strCategory, strLabel)
        strExistingLabelOwner = dictLabelOwner.get(tupleLabel)
        if strExistingLabelOwner is not None:
            raise ValueError(
                f"snippets.{snippetKey}.label duplicates {strExistingLabelOwner!r} within category {strCategory!r}."
            )
        dictLabelOwner[tupleLabel] = snippetKey

        strPrefix = _validate_single_line_string(
            snippetValue.get("prefix"),
            f"snippets.{snippetKey}.prefix",
        )
        strExistingPrefixOwner = dictPrefixOwner.get(strPrefix)
        if strExistingPrefixOwner is not None:
            raise ValueError(
                f"snippets.{snippetKey}.prefix duplicates {strExistingPrefixOwner!r}."
            )
        dictPrefixOwner[strPrefix] = snippetKey

        bodyValue = snippetValue.get("body")
        if (
            not isinstance(bodyValue, list)
            or not bodyValue
            or not all(isinstance(line, str) for line in bodyValue)
            or all(line.strip() == "" for line in bodyValue)
        ):
            raise ValueError(
                f"snippets.{snippetKey}.body must be a non-empty array of strings."
            )
        listBody = list(bodyValue)

        description = snippetValue.get("description")
        if not isinstance(description, str) or description.strip() == "":
            raise ValueError(
                f"snippets.{snippetKey}.description must be a non-empty string."
            )

        insertionMode = snippetValue.get("insertionMode")
        if insertionMode not in {"line", "cursor"}:
            raise ValueError(
                f"snippets.{snippetKey}.insertionMode must be 'line' or 'cursor'."
            )

        dictImports = _validate_catalog_imports(
            snippetValue.get("imports"),
            f"snippets.{snippetKey}.imports",
            packageName=manifestObj.packageName,
            publicModuleSet=setModule,
        )
        strModuleName = strCategory[len(strCategoryPrefix) :]
        if strModuleName not in dictImports.get(manifestObj.packageName, []):
            raise ValueError(
                f"snippets.{snippetKey}.imports must include its own public Module {strModuleName!r}."
            )

        setUsedCategory.add(strCategory)
        dictSnippet[snippetKey] = {
            "category": strCategory,
            "label": strLabel,
            "prefix": strPrefix,
            "body": listBody,
            "description": description,
            "insertionMode": insertionMode,
            "imports": dictImports,
        }

    if setCategory != setUsedCategory:
        raise ValueError(
            "categoryOrder must contain exactly the categories used by the final Snippets."
        )

    listExpectedCategoryOrder = [
        f"{manifestObj.packageName}_{moduleName}"
        for moduleName in listModuleOrder
        if f"{manifestObj.packageName}_{moduleName}" in setUsedCategory
    ]
    if listCategoryOrder != listExpectedCategoryOrder:
        raise ValueError(
            "categoryOrder must follow the Component import source Module order."
        )

    return {
        "schemaVersion": 1,
        "categoryOrder": listCategoryOrder,
        "categoryIcons": dictCategoryIcon,
        "importSources": {
            manifestObj.packageName: {
                "order": listModuleOrder,
                "aliasMode": "source_module",
            }
        },
        "snippets": dictSnippet,
    }


def _validate_component_wheel(
    wheelFilePath: Path,
    manifestObj: Info_ProjectManifest_Component,
    snippetCatalogDict: DictSnippet_CatalogFile,
) -> str:
    dictPublishedManifest = build_project_manifest_dict(manifestObj)
    strDistInfoFolder, strExpectedWheelFileName = get_component_wheel_names(
        manifestObj.packageName,
        manifestObj.version,
    )

    if wheelFilePath.name != strExpectedWheelFileName:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message="Component Wheel filename does not match its Component metadata.",
            details={
                "wheelFileName": wheelFilePath.name,
                "expectedWheelFileName": strExpectedWheelFileName,
            },
        )

    try:
        dictExpectedSnippetCatalog = _validate_snippet_catalog(
            snippetCatalogDict, manifestObj
        )

        normalizedName, versionObj, buildTag, tagSet = parse_wheel_filename(
            wheelFilePath.name
        )
        if normalizedName != canonicalize_name(manifestObj.packageName):
            raise ValueError("Wheel distribution name does not match packageName.")
        if versionObj != Version(manifestObj.version):
            raise ValueError("Wheel version does not match component.json.")
        if buildTag:
            raise ValueError("LiberRPA Component Wheels cannot use a build tag.")
        if tagSet != frozenset({TAG_COMPONENT_WHEEL}):
            raise ValueError(
                f"Wheel must use the {STR_COMPONENT_WHEEL_TAG} compatibility tag."
            )

        with ZipFile(wheelFilePath, mode="r") as wheelObj:
            strBadFile = wheelObj.testzip()
            if strBadFile is not None:
                raise ValueError(f"Wheel ZIP integrity check failed: {strBadFile!r}.")

            strMetadataPath = f"{strDistInfoFolder}/METADATA"
            strWheelMetadataPath = f"{strDistInfoFolder}/WHEEL"
            strLicensePath = f"{strDistInfoFolder}/licenses/LICENSE"
            strManifestFilePath = f"{strDistInfoFolder}/component.json"
            strCatalogPath = f"{strDistInfoFolder}/snippets_catalog.json"
            strRecordPath = f"{strDistInfoFolder}/RECORD"

            listInfo = wheelObj.infolist()
            listArchivePath = [infoObj.filename for infoObj in listInfo]
            setArchivePath = set(listArchivePath)

            if len(setArchivePath) != len(listArchivePath):
                raise ValueError("Wheel contains duplicate paths.")

            dictCaseInsensitivePath: dict[str, str] = {}
            for infoObj in listInfo:
                strArchivePath = infoObj.filename
                validate_archive_path(strArchivePath)

                if infoObj.compress_type != ZIP_STORED:
                    raise ValueError(
                        f"Wheel file must use ZIP_STORED compression: {strArchivePath!r}."
                    )
                if infoObj.date_time != _TUPLE_ZIP_TIMESTAMP:
                    raise ValueError(
                        f"Wheel file has a non-deterministic timestamp: {strArchivePath!r}."
                    )
                if (
                    infoObj.create_system != 3
                    or infoObj.external_attr != _INT_ZIP_FILE_MODE
                ):
                    raise ValueError(
                        f"Wheel file has invalid permission metadata: {strArchivePath!r}."
                    )

                intFileType = stat.S_IFMT(infoObj.external_attr >> 16)
                if intFileType == stat.S_IFLNK:
                    raise ValueError(
                        f"Wheel cannot contain symbolic links: {strArchivePath!r}."
                    )

                strCaseInsensitivePath = strArchivePath.casefold()
                strExistingPath = dictCaseInsensitivePath.get(strCaseInsensitivePath)
                if strExistingPath is not None:
                    raise ValueError(
                        f"Wheel contains paths that conflict on Windows: {strExistingPath!r}, {strArchivePath!r}."
                    )
                dictCaseInsensitivePath[strCaseInsensitivePath] = strArchivePath

                pathArchiveEntry = PurePosixPath(strArchivePath)
                if pathArchiveEntry.parts[0] not in {
                    manifestObj.packageName,
                    strDistInfoFolder,
                }:
                    raise ValueError(
                        f"Wheel contains an unexpected top-level path: {strArchivePath!r}."
                    )

                if pathArchiveEntry.parts[0] == manifestObj.packageName:
                    if "__pycache__" in pathArchiveEntry.parts:
                        raise ValueError(
                            f"Wheel cannot contain __pycache__: {strArchivePath!r}."
                        )
                    if pathArchiveEntry.suffix.casefold() in _SET_IGNORED_FILE_SUFFIX:
                        raise ValueError(
                            f"Wheel cannot contain ignored Python cache files: {strArchivePath!r}."
                        )
                    if pathArchiveEntry.suffix.casefold() in _SET_FORBIDDEN_FILE_SUFFIX:
                        raise ValueError(
                            f"Wheel contains an unsupported file type: {strArchivePath!r}."
                        )

            setExpectedDistInfoPath = {
                strMetadataPath,
                strWheelMetadataPath,
                strLicensePath,
                strManifestFilePath,
                strCatalogPath,
                strRecordPath,
            }
            setRequiredPath = {
                f"{manifestObj.packageName}/__init__.py",
                f"{manifestObj.packageName}/py.typed",
                *setExpectedDistInfoPath,
            }
            listMissingPath = sorted(setRequiredPath - setArchivePath)
            if listMissingPath:
                raise ValueError(f"Wheel is missing required files: {listMissingPath}.")

            setActualDistInfoPath = {
                strArchivePath
                for strArchivePath in setArchivePath
                if PurePosixPath(strArchivePath).parts[0] == strDistInfoFolder
            }
            if setActualDistInfoPath != setExpectedDistInfoPath:
                raise ValueError(
                    "Wheel .dist-info files do not match the LiberRPA Component Wheel structure. "
                    f"Unexpected: {sorted(setActualDistInfoPath - setExpectedDistInfoPath)}."
                )

            listExpectedArchivePath = [
                *sorted(setArchivePath - {strRecordPath}),
                strRecordPath,
            ]
            if listArchivePath != listExpectedArchivePath:
                raise ValueError(
                    "Wheel files are not stored in the deterministic LiberRPA order."
                )

            metadataObj = _read_metadata(wheelObj.read(strMetadataPath), "METADATA")
            if metadataObj.get("Metadata-Version") != "2.4":
                raise ValueError("Wheel METADATA must use Metadata-Version 2.4.")
            if canonicalize_name(metadataObj.get("Name", "")) != canonicalize_name(
                manifestObj.packageName
            ):
                raise ValueError("Wheel METADATA Name does not match packageName.")
            if Version(metadataObj.get("Version", "")) != Version(manifestObj.version):
                raise ValueError("Wheel METADATA Version does not match component.json.")
            if metadataObj.get_all("Requires-Dist"):
                raise ValueError(
                    "LiberRPA Component Wheels cannot contain Requires-Dist metadata."
                )
            if metadataObj.get_all("License-File") != ["LICENSE"]:
                raise ValueError("Wheel METADATA must declare LICENSE.")

            wheelMetadataObj = _read_metadata(
                wheelObj.read(strWheelMetadataPath), "WHEEL"
            )
            if wheelMetadataObj.get("Wheel-Version") != "1.0":
                raise ValueError("Wheel-Version must be 1.0.")
            if wheelMetadataObj.get("Root-Is-Purelib", "").casefold() != "true":
                raise ValueError("Root-Is-Purelib must be true.")
            if wheelMetadataObj.get_all("Tag") != [STR_COMPONENT_WHEEL_TAG]:
                raise ValueError(
                    f"WHEEL must contain exactly one Tag: {STR_COMPONENT_WHEEL_TAG}."
                )

            embeddedManifest = parse_json(
                wheelObj.read(strManifestFilePath).decode("utf-8", errors="strict")
            )
            if embeddedManifest != dictPublishedManifest:
                raise ValueError(
                    "Embedded component.json does not match the published Component Manifest."
                )

            embeddedCatalog = parse_json(
                wheelObj.read(strCatalogPath).decode("utf-8", errors="strict")
            )
            dictEmbeddedSnippetCatalog = _validate_snippet_catalog(
                embeddedCatalog, manifestObj
            )
            if dictEmbeddedSnippetCatalog != dictExpectedSnippetCatalog:
                raise ValueError(
                    "Embedded snippets_catalog.json does not match the generated catalog."
                )

            validate_record(
                archivePathSet=setArchivePath,
                recordPath=strRecordPath,
                readArchiveFile=wheelObj.read,
            )
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, ValueError) as e:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Built Component Wheel is invalid: {wheelFilePath}",
            details={"reason": str(e)},
        ) from e

    return calculate_file_sha256(wheelFilePath)


def inspect_component_wheel(wheelFilePath: Path) -> Info_ComponentWheel:
    if is_file_invalid(wheelFilePath):
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Component Wheel file was not found or is invalid: {wheelFilePath}",
        )

    try:
        with ZipFile(wheelFilePath, mode="r") as wheelObj:
            listManifestFilePath = [
                infoObj.filename
                for infoObj in wheelObj.infolist()
                if PurePosixPath(infoObj.filename).name == "component.json"
                and PurePosixPath(infoObj.filename).parent.name.endswith(".dist-info")
            ]

            if len(listManifestFilePath) != 1:
                raise ValueError(
                    "Wheel must contain exactly one component.json directly inside its .dist-info folder."
                )

            strManifestFilePath = listManifestFilePath[0]
            pathDistInfoFolder = PurePosixPath(strManifestFilePath).parent
            strCatalogPath = (pathDistInfoFolder / "snippets_catalog.json").as_posix()

            embeddedManifest = parse_json(
                wheelObj.read(strManifestFilePath).decode("utf-8", errors="strict")
            )
            manifestObj = parse_component_manifest(
                embeddedManifest,
                sourceName=strManifestFilePath,
            )

            embeddedCatalog = parse_json(
                wheelObj.read(strCatalogPath).decode("utf-8", errors="strict")
            )
            dictSnippetCatalog = _validate_snippet_catalog(embeddedCatalog, manifestObj)
    except ComponentManagementError:
        raise
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, ValueError) as e:
        raise ComponentManagementError(
            code="wheel_validation_failed",
            message=f"Component Wheel is invalid: {wheelFilePath}",
            details={"reason": str(e)},
        ) from e

    strSha256 = _validate_component_wheel(
        wheelFilePath=wheelFilePath,
        manifestObj=manifestObj,
        snippetCatalogDict=dictSnippetCatalog,
    )

    return Info_ComponentWheel(
        manifest=manifestObj,
        snippetCatalog=dictSnippetCatalog,
        wheelFileName=wheelFilePath.name,
        sha256=strSha256,
    )
