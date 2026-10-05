# FileName: ValidateVersionMetadata.py
import json
import sys
from typing import TypedDict, cast

from packaging.specifiers import SpecifierSet
from packaging.version import Version


class VersionMetadata(TypedDict):
    version: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


def _validate_specifier(specifier: str) -> None:
    if "===" in specifier:
        raise ValueError("The arbitrary equality operator '===' is not supported.")
    if not SpecifierSet(specifier):
        raise ValueError("Version specifier cannot be empty.")


def _main() -> None:
    # The caller has validated the metadata structure; packaging handles version syntax.
    dictMetadata = cast(VersionMetadata, json.load(sys.stdin))
    strVersion = str(Version(dictMetadata["version"]))
    _validate_specifier(dictMetadata["requiresLiberrpa"])
    for strSpecifier in dictMetadata["componentDependencies"].values():
        _validate_specifier(strSpecifier)
    print(strVersion)


if __name__ == "__main__":
    try:
        _main()
    except (TypeError, ValueError) as e:
        sys.exit(str(e))
