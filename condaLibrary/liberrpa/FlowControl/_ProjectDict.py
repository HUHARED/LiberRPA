# FileName: _ProjectDict.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.UI._UiDict import DictPosition
from typing import TypedDict, Literal, NotRequired, Any


class DictProject_Node_Properties(TypedDict):
    pyFile: NotRequired[str]
    condition: NotRequired[str]


""" class DictPyInfo(TypedDict):
    text: str
    pyFile: str


class DictConditionInfo(TypedDict):
    text: str
    condition: str """


class DictProject_Node(TypedDict):
    id: str
    type: Literal["Start", "SubStart", "Block", "Choose", "End"]
    x: int
    y: int
    text: str
    properties: DictProject_Node_Properties


class DictProject_Edge(TypedDict):
    id: str
    type: Literal["CommonLine", "TrueLine", "FalseLine", "ExceptionLine"]
    sourceNodeId: str
    targetNodeId: str
    text: str
    startPoint: DictPosition
    endPoint: DictPosition


class DictProject_Original(TypedDict):
    nodes: list[DictProject_Node]
    edges: list[DictProject_Edge]
    executeMode: Literal["Run", "Debug"]
    logLevel: Literal["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    recordVideo: bool
    stopShortcut: bool
    highlightUi: bool
    customPrjArgs: list[tuple[str, Any]]


""" class DictProject(TypedDict):
    nodes: list[DictProject_Node]
    edges: list[DictProject_Edge]
    logLevel: Literal["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    recordVideo: bool
    stopShortcut: bool
    customPrjArgs: dict[str, Any]
 """
