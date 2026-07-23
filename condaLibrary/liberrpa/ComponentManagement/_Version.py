# FileName: _Version.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def normalize_version(version: str) -> str:
    try:
        return str(Version(version))
    except InvalidVersion as e:
        raise ValueError(f"Invalid PEP 440 version: {version!r}.") from e


def normalize_specifier(specifier: str) -> str:
    if specifier == "":
        raise ValueError("Version specifier cannot be empty.")

    if "===" in specifier:
        raise ValueError("The arbitrary equality operator '===' is not supported.")

    try:
        return str(SpecifierSet(specifier))
    except InvalidSpecifier as e:
        raise ValueError(f"Invalid PEP 440 version specifier: {specifier!r}.") from e
