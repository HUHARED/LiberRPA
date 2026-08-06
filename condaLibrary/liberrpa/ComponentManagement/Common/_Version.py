# FileName: _Version.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from importlib.metadata import PackageNotFoundError, version as get_package_version
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def normalize_pep440_version(version: str) -> str:
    try:
        return str(Version(version))
    except InvalidVersion as e:
        raise ValueError(f"Invalid PEP 440 version: {version!r}.") from e


def normalize_pep440_specifier(specifier: str) -> str:
    if specifier == "":
        raise ValueError("Version specifier cannot be empty.")

    if "===" in specifier:
        raise ValueError("The arbitrary equality operator '===' is not supported.")

    try:
        return str(SpecifierSet(specifier))
    except InvalidSpecifier as e:
        raise ValueError(f"Invalid PEP 440 version specifier: {specifier!r}.") from e


def get_installed_liberrpa_version() -> Version:
    try:
        return Version(get_package_version("liberrpa"))
    except PackageNotFoundError as e:
        raise ValueError(
            "The installed liberrpa package version could not be determined."
        ) from e
    except InvalidVersion as e:
        raise ValueError("The installed liberrpa package version is invalid.") from e
