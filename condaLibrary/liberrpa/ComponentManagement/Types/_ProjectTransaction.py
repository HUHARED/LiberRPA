# FileName: _ProjectTransaction.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Manifest import Str_ProjectTypeValue

from typing import Literal, NotRequired, TypedDict


type Str_ProjectTransaction_State = Literal["prepared", "committing", "manifestCommitted"]


class DictProjectTransaction_Snapshot(TypedDict):
    manifestSha256: str
    componentsLockExists: bool
    componentsPathExists: bool
    componentsLockSha256: NotRequired[str]


class DictProjectTransaction_ApplyDependencyPlan(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["applyDependencyPlan"]
    state: Str_ProjectTransaction_State
    projectType: Str_ProjectTypeValue
    manifestFile: Literal["flow.json", "component.json"]
    planSha256: str
    source: DictProjectTransaction_Snapshot
    target: DictProjectTransaction_Snapshot


class DictProjectTransaction_RepairComponents(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["repairProjectComponents"]
    state: Str_ProjectTransaction_State
    projectType: Str_ProjectTypeValue
    manifestFile: Literal["flow.json", "component.json"]
    source: DictProjectTransaction_Snapshot
    target: DictProjectTransaction_Snapshot


type DictProjectTransaction = DictProjectTransaction_ApplyDependencyPlan | DictProjectTransaction_RepairComponents
