# FileName: _Version.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from importlib.metadata import PackageNotFoundError, version as get_package_version
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def normalize_pep440_version(version: str) -> str:
    try:
        return str(Version(version))
    except InvalidVersion as e:
        raise ValueError(f"Invalid PEP 440 version: {version!r}.") from e


def _get_specifier_sort_group(specifierObj: Specifier) -> int:
    if specifierObj.operator in {">", ">="}:
        return 0
    if specifierObj.operator in {"<", "<="}:
        return 2
    return 1


def _normalize_pep440_specifier_item(specifierObj: Specifier) -> str:
    strVersion = specifierObj.version
    boolWildcardVersion = strVersion.endswith(".*")
    strVersionToNormalize = strVersion[:-2] if boolWildcardVersion else strVersion
    strNormalizedVersion = normalize_pep440_version(strVersionToNormalize)

    if boolWildcardVersion:
        strNormalizedVersion += ".*"

    return f"{specifierObj.operator}{strNormalizedVersion}"


def normalize_pep440_specifier(specifier: str) -> str:
    if specifier == "":
        raise ValueError("Version specifier cannot be empty.")

    if "===" in specifier:
        raise ValueError("The arbitrary equality operator '===' is not supported.")

    try:
        # Validate the complete set first, then normalize each item while retaining the user's relative order inside lower, middle, and upper-bound groups.
        _ = SpecifierSet(specifier)
        listSpecifierObj = [
            Specifier(strItem.strip())
            for strItem in specifier.split(",")
            if strItem.strip() != ""
        ]
    except InvalidSpecifier as e:
        raise ValueError(f"Invalid PEP 440 version specifier: {specifier!r}.") from e

    if not listSpecifierObj:
        raise ValueError("Version specifier cannot be empty.")

    listUniqueSpecifier: list[tuple[Specifier, str]] = []
    setNormalizedSpecifier: set[str] = set()
    for specifierObj in listSpecifierObj:
        strNormalizedSpecifier = _normalize_pep440_specifier_item(specifierObj)
        if strNormalizedSpecifier in setNormalizedSpecifier:
            continue
        setNormalizedSpecifier.add(strNormalizedSpecifier)
        listUniqueSpecifier.append((specifierObj, strNormalizedSpecifier))

    listUniqueSpecifier.sort(
        key=lambda tupleSpecifier: _get_specifier_sort_group(tupleSpecifier[0])
    )
    return ",".join(
        strNormalizedSpecifier for _, strNormalizedSpecifier in listUniqueSpecifier
    )


def get_default_requires_liberrpa(versionObj: Version) -> str:
    strEpochPrefix = f"{versionObj.epoch}!" if versionObj.epoch != 0 else ""

    strMinimumVersion = (
        versionObj.public
        if versionObj.is_prerelease or versionObj.is_devrelease
        else f"{strEpochPrefix}{versionObj.major}.{versionObj.minor}"
    )

    if versionObj.major < 1:
        strMaximumVersion = f"{strEpochPrefix}{versionObj.major}.{versionObj.minor + 1}"
    else:
        strMaximumVersion = f"{strEpochPrefix}{versionObj.major + 1}.0"

    return normalize_pep440_specifier(f">={strMinimumVersion},<{strMaximumVersion}")


def get_installed_liberrpa_version() -> Version:
    try:
        return Version(get_package_version("liberrpa"))
    except PackageNotFoundError as e:
        raise ValueError(
            "The installed liberrpa package version could not be determined."
        ) from e
    except InvalidVersion as e:
        raise ValueError("The installed liberrpa package version is invalid.") from e
