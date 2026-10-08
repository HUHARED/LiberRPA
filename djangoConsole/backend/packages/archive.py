# FileName: archive.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import stat
import zipfile
import zlib
from typing import BinaryIO
from uuid import UUID

from django.core.exceptions import ValidationError
from pydantic import ValidationError as ContractValidationError
from packaging.specifiers import Specifier, SpecifierSet
from packaging.version import Version

from console_project.validators import validate_json_text, validate_windows_name

from .contracts import (
    MAX_PACKAGE_BYTES,
    INT_DESCRIPTION_MAX_LENGTH,
    INT_VERSION_SUMMARY_MAX_LENGTH,
    RunSettings,
)

_INT_MAX_ENTRY_COUNT = 20000
_INT_MAX_EXPANDED_BYTES = 2 * 1024**3
_INT_MAX_METADATA_BYTES = 2 * 1024**2


def _parse_root_json(archive: zipfile.ZipFile, name: str) -> dict:
    try:
        entry = archive.getinfo(name)
    except KeyError:
        raise ValidationError(f"The Package must contain {name} at its root.") from None
    if entry.file_size > _INT_MAX_METADATA_BYTES:
        raise ValidationError(f"{name} exceeds the 2 MiB metadata limit.")
    value = json.loads(
        archive.read(entry).decode("utf-8-sig"),
        parse_constant=lambda _value: (_ for _ in ()).throw(
            ValueError("JSON numbers must be finite.")
        ),
    )
    if not isinstance(value, dict):
        raise ValidationError(f"{name} must be a JSON object.")
    return value


def _require_text(
    value: object,
    label: str,
    maxLength: int | None = None,
    allowEmpty: bool = False,
    singleLine: bool = True,
) -> str:
    if (
        not isinstance(value, str)
        or (maxLength is not None and len(value) > maxLength)
        or (not value and not allowEmpty)
        or (singleLine and (value != value.strip() or "\n" in value or "\r" in value))
    ):
        raise ValidationError(f"Invalid {label}.")
    validate_json_text(value)
    return value


def _normalize_version_specifier(value: object, label: str) -> str:
    strValue = _require_text(value, label)
    if "===" in strValue:
        raise ValueError("The arbitrary equality operator '===' is not supported.")
    SpecifierSet(strValue)
    # NOTE: Match liberrpa.ComponentManagement.Common._Version normalization, including stable lower/middle/upper-bound ordering.
    dictSpecifier: dict[str, int] = {}
    for strItem in strValue.split(","):
        if not strItem.strip():
            continue
        specifier = Specifier(strItem.strip())
        strVersion = specifier.version
        boolWildcard = strVersion.endswith(".*")
        strNormalizedVersion = str(
            Version(strVersion[:-2] if boolWildcard else strVersion)
        )
        strNormalized = (
            f"{specifier.operator}{strNormalizedVersion}{'.*' if boolWildcard else ''}"
        )
        if specifier.operator in (">", ">="):
            intGroup = 0
        elif specifier.operator in ("<", "<="):
            intGroup = 2
        else:
            intGroup = 1
        dictSpecifier[strNormalized] = intGroup
    if not dictSpecifier:
        raise ValueError("Version specifier cannot be empty.")
    return ",".join(sorted(dictSpecifier, key=lambda strItem: dictSpecifier[strItem]))


def _parse_component_dependencies(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValidationError("componentDependencies must be an object.")
    dictDependency: dict[str, str] = {}
    for strId, specifier in value.items():
        uuidObj = UUID(strId)
        if uuidObj.version != 4 or str(uuidObj) != strId:
            raise ValidationError(
                "Component IDs must be canonical lowercase UUID v4 values."
            )
        dictDependency[strId] = _normalize_version_specifier(
            specifier, f"componentDependencies.{strId}"
        )
    return dict(sorted(dictDependency.items()))


def _read_metadata(archive: zipfile.ZipFile) -> dict:
    flow = _parse_root_json(archive, "flow.json")
    manifest = _parse_root_json(archive, ".liberrpa-package.json")
    project = _parse_root_json(archive, "project.flow")
    if (
        set(flow)
        != {
            "schemaVersion",
            "name",
            "version",
            "description",
            "requiresLiberrpa",
            "componentDependencies",
        }
        or type(flow["schemaVersion"]) is not int
        or flow["schemaVersion"] != 1
    ):
        raise ValidationError("The Package requires a valid flow.json schemaVersion 1.")
    if (
        set(manifest) != {"schemaVersion", "versionSummary"}
        or type(manifest["schemaVersion"]) is not int
        or manifest["schemaVersion"] != 1
    ):
        raise ValidationError(
            "The Package requires a valid .liberrpa-package.json schemaVersion 1."
        )
    if (
        set(project)
        != {
            "nodes",
            "edges",
            "executeMode",
            "logLevel",
            "recordVideo",
            "stopShortcut",
            "highlightUi",
            "customPrjArgs",
        }
        or not isinstance(project["nodes"], list)
        or not isinstance(project["edges"], list)
        or project["executeMode"] not in ("Run", "Debug")
    ):
        raise ValidationError("The Package contains an invalid project.flow.")
    strName = _require_text(flow["name"], "project name")
    strVersion = str(Version(_require_text(flow["version"], "version")))
    validate_windows_name(f"{strName}_{strVersion}.rpa.zip")
    runSettings = RunSettings(
        builtin_log_level=project["logLevel"],
        builtin_record_video=project["recordVideo"],
        builtin_stop_shortcut=project["stopShortcut"],
        builtin_highlight_ui=project["highlightUi"],
        custom_prj_args=project["customPrjArgs"],
    )
    return {
        "project_name": strName,
        "version": strVersion,
        "description": _require_text(
            flow["description"], "description", INT_DESCRIPTION_MAX_LENGTH, True, False
        ),
        "version_summary": _require_text(
            manifest["versionSummary"],
            "version summary",
            INT_VERSION_SUMMARY_MAX_LENGTH,
            True,
        ),
        "requires_liberrpa": _normalize_version_specifier(
            flow["requiresLiberrpa"], "requiresLiberrpa"
        ),
        "component_dependencies": _parse_component_dependencies(
            flow["componentDependencies"]
        ),
        "argument_names": [
            listArgument[0] for listArgument in runSettings.custom_prj_args
        ],
        **runSettings.model_dump(mode="json"),
    }


def read_package_archive(handle: BinaryIO) -> dict:
    """Validate the uploaded file boundary once without extracting executable content."""
    try:
        with zipfile.ZipFile(handle) as archive:
            listEntry = archive.infolist()
            if len(listEntry) > _INT_MAX_ENTRY_COUNT:
                raise ValidationError("The Package contains more than 20,000 entries.")
            dictPath: dict[str, bool] = {}
            setParent: set[str] = set()
            intExpandedBytes = 0
            for entry in listEntry:
                strName = entry.filename.replace("\\", "/").removesuffix("/")
                listPart = strName.split("/")
                if any(strPart in ("", ".", "..") for strPart in listPart):
                    raise ValidationError(
                        "The Package contains an invalid relative path."
                    )
                for strPart in listPart:
                    validate_windows_name(strPart)
                strKey = strName.lower()
                if strKey in dictPath or (not entry.is_dir() and strKey in setParent):
                    raise ValidationError(
                        "The Package contains duplicate or conflicting paths."
                    )
                for intIndex in range(1, len(listPart)):
                    strParent = "/".join(listPart[:intIndex]).lower()
                    if dictPath.get(strParent) is False:
                        raise ValidationError("The Package uses a file as a directory.")
                    setParent.add(strParent)
                dictPath[strKey] = entry.is_dir()
                intMode = stat.S_IFMT(entry.external_attr >> 16)
                if entry.flag_bits & 1 or intMode not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValidationError(
                        "Encrypted and special ZIP entries are not supported."
                    )
                intExpandedBytes += entry.file_size
                if (
                    entry.file_size > MAX_PACKAGE_BYTES
                    or intExpandedBytes > _INT_MAX_EXPANDED_BYTES
                ):
                    raise ValidationError(
                        "The Package exceeds its uncompressed size limit."
                    )
            # Stream every member to verify CRC and actual byte counts without retaining expanded content.
            for entry in listEntry:
                intReadBytes = 0
                with archive.open(entry) as entryHandle:
                    while chunk := entryHandle.read(1024 * 1024):
                        intReadBytes += len(chunk)
                        if intReadBytes > entry.file_size:
                            raise ValidationError(
                                "A ZIP entry exceeds its declared size."
                            )
                if intReadBytes != entry.file_size:
                    raise ValidationError("A ZIP entry has an inconsistent size.")
            return _read_metadata(archive)
    except (zlib.error, EOFError):
        raise ValidationError(
            "The Package archive contains damaged or incomplete data."
        ) from None
    except (
        zipfile.BadZipFile,
        UnicodeError,
        ValueError,
        KeyError,
        RuntimeError,
        ContractValidationError,
        NotImplementedError,
    ) as e:
        raise ValidationError(f"Invalid Package archive: {e}") from None
