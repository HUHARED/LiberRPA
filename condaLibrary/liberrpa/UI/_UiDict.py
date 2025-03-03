# FileName: _UiDict.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from typing import TypedDict, Literal, NotRequired


class DictPosition(TypedDict):
    x: int
    y: int


class DictPositionAndSize(DictPosition):
    width: int
    height: int


# HTML
DictHtmlSecondaryAttr = TypedDict(
    "DictHtmlSecondaryAttr",
    {
        "secondary-x": str,
        "secondary-y": str,
        "secondary-width": str,
        "secondary-height": str,
    },
)

DictSpecHtmlOriginal = TypedDict(
    "DictSpecHtmlOriginal",
    {
        "tagName": NotRequired[str],
        "id": NotRequired[str],
        "className": NotRequired[str],
        "type": NotRequired[str],
        "value": NotRequired[str],
        "name": NotRequired[str],
        "aria-label": NotRequired[str],
        "aria-labelledby": NotRequired[str],
        "checked": NotRequired[Literal["true", "indeterminate", "false"]],
        "disabled": NotRequired[Literal["true", "false"]],
        "href": NotRequired[str],
        "src": NotRequired[str],
        "alt": NotRequired[str],
        "isHidden": NotRequired[Literal["true", "false"]],
        "isDisplayedNone": NotRequired[Literal["true", "false"]],
        "innerText": NotRequired[str],
        "directText": NotRequired[str],
        "parentId": NotRequired[str],
        "parentClass": NotRequired[str],
        "parentName": NotRequired[str],
        "isLeaf": NotRequired[Literal["true", "false"]],
        "tableRowIndex": NotRequired[str],
        "tableColumnIndex": NotRequired[str],
        "tableColumnName": NotRequired[str],
        "childIndex": NotRequired[str],
        "documentIndex": NotRequired[str],
        "path": NotRequired[str],
    },
)

DictSpecHtml = TypedDict(
    # It adds some -regex from DictSpecHtmlOriginal
    "DictSpecHtml",
    {
        "tagName": NotRequired[str],
        "tagName-regex": NotRequired[str],
        "id": NotRequired[str],
        "id-regex": NotRequired[str],
        "className": NotRequired[str],
        "className-regex": NotRequired[str],
        "type": NotRequired[str],
        "type-regex": NotRequired[str],
        "value": NotRequired[str],
        "value-regex": NotRequired[str],
        "name": NotRequired[str],
        "name-regex": NotRequired[str],
        "aria-label": NotRequired[str],
        "aria-label-regex": NotRequired[str],
        "aria-labelledby": NotRequired[str],
        "aria-labelledby-regex": NotRequired[str],
        "checked": NotRequired[Literal["true", "indeterminate", "false"]],
        "checked-regex": NotRequired[str],
        "disabled": NotRequired[Literal["true", "false"]],
        "disabled-regex": NotRequired[str],
        "href": NotRequired[str],
        "href-regex": NotRequired[str],
        "src": NotRequired[str],
        "src-regex": NotRequired[str],
        "alt": NotRequired[str],
        "alt-regex": NotRequired[str],
        "isHidden": NotRequired[Literal["true", "false"]],
        "isHidden-regex": NotRequired[str],
        "isDisplayedNone": NotRequired[Literal["true", "false"]],
        "isDisplayedNone-regex": NotRequired[str],
        "innerText": NotRequired[str],
        "innerText-regex": NotRequired[str],
        "directText": NotRequired[str],
        "directText-regex": NotRequired[str],
        "parentId": NotRequired[str],
        "parentId-regex": NotRequired[str],
        "parentClass": NotRequired[str],
        "parentClass-regex": NotRequired[str],
        "parentName": NotRequired[str],
        "parentName-regex": NotRequired[str],
        "isLeaf": NotRequired[Literal["true", "false"]],
        "isLeaf-regex": NotRequired[str],
        "tableRowIndex": NotRequired[str],
        "tableRowIndex-regex": NotRequired[str],
        "tableColumnIndex": NotRequired[str],
        "tableColumnIndex-regex": NotRequired[str],
        "tableColumnName": NotRequired[str],
        "tableColumnName-regex": NotRequired[str],
        "childIndex": NotRequired[str],
        "childIndex-regex": NotRequired[str],
        "documentIndex": NotRequired[str],
        "documentIndex-regex": NotRequired[str],
        "path": NotRequired[str],
        "path-regex": NotRequired[str],
    },
)


class DictHtmlAttr(DictSpecHtmlOriginal, DictHtmlSecondaryAttr):
    pass


# UIA
DictUiaSecondaryAttr = TypedDict(
    # All item in tupleSecondaryAttr, and x, y, width, height.
    "DictUiaSecondaryAttr",
    {
        "secondary-ControlType": NotRequired[str],
        "secondary-AutomationId": NotRequired[str],
        "secondary-Culture": NotRequired[str],
        "secondary-HasKeyboardFocus": NotRequired[Literal["true", "false"]],
        "secondary-IsContentElement": NotRequired[Literal["true", "false"]],
        "secondary-IsControlElement": NotRequired[Literal["true", "false"]],
        "secondary-IsDataValidForForm": NotRequired[Literal["true", "false"]],
        "secondary-IsEnabled": NotRequired[Literal["true", "false"]],
        "secondary-IsKeyboardFocusable": NotRequired[Literal["true", "false"]],
        "secondary-IsOffscreen": NotRequired[Literal["true", "false"]],
        "secondary-IsPassword": NotRequired[Literal["true", "false"]],
        "secondary-IsRequiredForForm": NotRequired[Literal["true", "false"]],
        "secondary-ItemStatus": NotRequired[str],
        "secondary-ItemType": NotRequired[str],
        "secondary-LocalizedControlType": NotRequired[str],
        "secondary-NativeWindowHandle": str,
        "secondary-Orientation": NotRequired[str],
        "secondary-ProcessId": str,
        "secondary-ProviderDescription": NotRequired[str],
        "secondary-x": str,
        "secondary-y": str,
        "secondary-width": str,
        "secondary-height": str,
    },
)


class DictUiaNonWindowPrimaryAttrBasic(TypedDict):
    # FrameworkId is a item tuplePrimaryAttr, but it is deleted in Non-Window, but Window keeps. To make the final selector concise.
    ControlTypeName: str
    Name: str
    AcceleratorKey: NotRequired[str]
    AccessKey: NotRequired[str]
    AriaProperties: NotRequired[str]
    AriaRole: NotRequired[str]
    ClassName: NotRequired[str]
    HelpText: NotRequired[str]


class DictUiaPrimaryAttrBasic(DictUiaNonWindowPrimaryAttrBasic):
    FrameworkId: str
    ProcessName: str


class DictUiaWindowPrimaryAttrBasic(DictUiaNonWindowPrimaryAttrBasic):
    # All uia elements have the 2 attributes, but selector can ignore them, so make them NotRequired.
    FrameworkId: NotRequired[str]  # It's a direct attribute
    ProcessName: NotRequired[str]  # It's generate by FrameworkId.


class DictUiaAttr(DictUiaPrimaryAttrBasic, DictUiaSecondaryAttr):
    pass


class DictSpecUiaOriginal(DictUiaNonWindowPrimaryAttrBasic):
    Depth: NotRequired[str]
    Index: NotRequired[str]


class DictSpecWindowOriginal(DictSpecUiaOriginal):
    FrameworkId: NotRequired[str]
    ProcessName: NotRequired[str]


class DictSpecUiaOriginalTemp(DictSpecWindowOriginal):
    NextLayerDepth: NotRequired[str]


DictSpecUia = TypedDict(
    # It adds some -regex from DictSpecUiaOriginal
    # Comment out some attributes that cannot use regex.
    "DictSpecUia",
    {
        "ControlTypeName": str,
        # "ControlTypeName-regex": str,
        "Name": NotRequired[str],
        "Name-regex": NotRequired[str],
        "AcceleratorKey": NotRequired[str],
        "AcceleratorKey-regex": NotRequired[str],
        "AccessKey": NotRequired[str],
        "AccessKey-regex": NotRequired[str],
        "AriaProperties": NotRequired[str],
        "AriaProperties-regex": NotRequired[str],
        "AriaRole": NotRequired[str],
        "AriaRole-regex": NotRequired[str],
        "ClassName": NotRequired[str],
        # "ClassName-regex": NotRequired[str],
        "HelpText": NotRequired[str],
        "HelpText-regex": NotRequired[str],
        "Depth": NotRequired[str],
        # "Depth-regex": NotRequired[str],
        "Index": NotRequired[str],
        "Index-regex": NotRequired[str],
    },
)

DictSpecWindow = TypedDict(
    # It adds some -regex from DictSpecUia
    # Comment out some attributes that cannot use regex.
    "DictSpecWindow",
    {
        "ControlTypeName": str,
        # "ControlTypeName-regex": str,
        "Name": NotRequired[str],
        "Name-regex": NotRequired[str],
        "AcceleratorKey": NotRequired[str],
        "AcceleratorKey-regex": NotRequired[str],
        "AccessKey": NotRequired[str],
        "AccessKey-regex": NotRequired[str],
        "AriaProperties": NotRequired[str],
        "AriaProperties-regex": NotRequired[str],
        "AriaRole": NotRequired[str],
        "AriaRole-regex": NotRequired[str],
        "ClassName": NotRequired[str],
        # "ClassName-regex": NotRequired[str],
        "HelpText": NotRequired[str],
        "HelpText-regex": NotRequired[str],
        "Depth": NotRequired[str],
        # "Depth-regex": NotRequired[str],
        "Index": NotRequired[str],
        "Index-regex": NotRequired[str],
        "FrameworkId": NotRequired[str],
        "FrameworkId-regex": NotRequired[str],
        "ProcessName": NotRequired[str],
        "ProcessName-regex": NotRequired[str],
    },
)

""" class DictSpecWindow(DictSpecUia):
    # NOTE: It should not have Depth, maybe create another class later.
    FrameworkId: NotRequired[str]
    ProcessName: NotRequired[str]
 """

# Image
DictImageAttr = TypedDict(
    "DictImageAttr",
    {
        "secondary-x": str,
        "secondary-y": str,
        "secondary-width": str,
        "secondary-height": str,
    },
)


class DictSepcImage(TypedDict):
    FileName: str
    Grayscale: str
    Confidence: str
    Index: NotRequired[str]


# Selector
class SelectorWindowOriginal(TypedDict):
    window: DictSpecWindowOriginal


class SelectorWindow(TypedDict):
    window: DictSpecWindow


class SelectorUiaOriginal(SelectorWindowOriginal):
    category: Literal["uia"]
    specification: list[DictSpecUiaOriginal]


class SelectorUia(SelectorWindow):
    category: Literal["uia"]
    specification: list[DictSpecUia]


class SelectorHtmlOriginal(SelectorWindowOriginal):
    category: Literal["html"]
    specification: list[DictSpecHtmlOriginal]


class SelectorHtml(SelectorWindow):
    category: Literal["html"]
    specification: list[DictSpecHtml]


class SelectorImage(SelectorWindow):
    category: Literal["image"]
    # Image has only one layer but use list to compatible with others.
    specification: list[DictSepcImage]


class DictElementTreeItem(TypedDict):
    id: int
    title: str
    spec: DictSpecUiaOriginal | DictSpecHtmlOriginal
    # Quoted forward references
    children: NotRequired[list["DictElementTreeItem"]]


# Dictionary for UI Anaylyzer.
class DictForUiAnalyzer(TypedDict):
    selector: SelectorWindow | SelectorUia | SelectorHtml
    attributes: DictUiaSecondaryAttr | DictHtmlSecondaryAttr
    preview: NotRequired[str]


if __name__ == "__main__":
    # print(DictSpecUiaOriginalTemp.__annotations__)
    # print(DictSpecUia.__annotations__)
    # print(DictSpecWindow.__annotations__)
    # print(DictElementTreeItem.__annotations__)

    temp: DictElementTreeItem = {
        "id": 1,
        "title": "test2",
        "spec": {
            "tagName": "h1",
            "innerText": "键盘按键测试",
            "directText": "键盘按键测试",
            "isLeaf": "true",
        },
        "children": [
            {
                "id": 2,
                "title": "test3",
                "spec": {
                    "tagName": "h1",
                    "innerText": "键盘按键测试",
                    "directText": "键盘按键测试",
                    "isLeaf": "true",
                },
            },
        ],
    }
    print(temp)

    temp2: DictElementTreeItem = {
        "id": 0,
        "title": "test1",
        "spec": {"tagName": "h1", "innerText": "键盘按键测试", "directText": "键盘按键测试", "isLeaf": "true"},
        "children": [
            {
                "id": 1,
                "title": "test2",
                "spec": {
                    "tagName": "h1",
                    "innerText": "键盘按键测试",
                    "directText": "键盘按键测 试",
                    "isLeaf": "true",
                },
            },
            {
                "id": 2,
                "title": "test3",
                "spec": {
                    "tagName": "h1",
                    "innerText": "键盘按键测试",
                    "directText": "键盘按键测试",
                    "isLeaf": "true",
                },
                "children": [
                    {
                        "id": 4,
                        "title": "test4",
                        "spec": {
                            "tagName": "h1",
                            "innerText": "键盘按键测试",
                            "directText": "键盘按键测试",
                            "isLeaf": "true",
                        },
                        "children": [
                            {
                                "id": 5,
                                "title": "test5",
                                "spec": {
                                    "tagName": "h1",
                                    "innerText": "键盘按键测试",
                                    "directText": "键盘按键测试",
                                    "isLeaf": "true",
                                },
                            }
                        ],
                    },
                ],
            },
        ],
    }

    print(temp2)
