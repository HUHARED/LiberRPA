# FileName: _Publish.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Info_Publish_PreparationCreated:
    status: Literal["preparationCreated"]
    projectPath: Path
    componentId: str
    packageName: str
    astSnippetsPath: Path
    snippetsConfigPath: Path
    generatedCount: int
    skippedCount: int
    warnings: list[DictComponentManagementWarning]


@dataclass(frozen=True)
class Info_Publish_Published:
    status: Literal["published", "alreadyPublished"]
    projectPath: Path
    componentId: str
    packageName: str
    version: str

    astSnippetsPath: Path
    snippetsConfigPath: Path
    generatedCount: int
    skippedCount: int
    warnings: list[DictComponentManagementWarning]

    excludedCount: int
    handWrittenCount: int
    finalCount: int

    wheelFileName: str
    sha256: str


type Info_PublishResult = Info_Publish_PreparationCreated | Info_Publish_Published
