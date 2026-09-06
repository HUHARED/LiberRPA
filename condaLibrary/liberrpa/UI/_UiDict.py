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


class DictHtmlSelectorRecommendationResult(TypedDict):
    allLayerAttributes: list[DictHtmlAttr]
    recommendedSpecification: list[DictSpecHtml]


# UIA
DictUiaSecondaryAttr = TypedDict(
    # All item in _TUPLE_SECONDARY_ATTR, and x, y, width, height.
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
        "secondary-NativeWindowHandle": NotRequired[str],
        "secondary-Orientation": NotRequired[str],
        "secondary-ProcessId": NotRequired[str],
        "secondary-ProviderDescription": NotRequired[str],
        "secondary-x": str,
        "secondary-y": str,
        "secondary-width": str,
        "secondary-height": str,
    },
)


class _DictUiaCommonPrimaryAttr(TypedDict):
    """Primary UIA attributes shared by collected data and selector layers."""

    ControlTypeName: str
    Name: NotRequired[str]
    AcceleratorKey: NotRequired[str]
    AccessKey: NotRequired[str]
    AriaProperties: NotRequired[str]
    AriaRole: NotRequired[str]
    ClassName: NotRequired[str]
    HelpText: NotRequired[str]


class DictUiaPrimaryAttr(_DictUiaCommonPrimaryAttr):
    """
    Primary attributes collected from one UIA control.

    LiberRPA attempts to collect FrameworkId for every control, but keeps it
    only in the window layer of generated selectors because it has usually been
    redundant within an anchored child search scope.

    ProcessName is derived from ProcessId when available. It is likewise kept
    only in the window layer of generated selectors.
    """

    FrameworkId: NotRequired[str]
    ProcessName: NotRequired[str]


class DictUiaAttr(DictUiaPrimaryAttr, DictUiaSecondaryAttr):
    pass


class DictElementTreeUiaAttr(_DictUiaCommonPrimaryAttr):
    """UIA attributes displayed in one UI Analyzer element-tree item."""

    pass


_DictSpecUiaCommon = TypedDict(
    # Exact and regex fields shared by window and non-window UIA selector layers.
    # Comment out some attributes that cannot use regex.
    "_DictSpecUiaCommon",
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
        "Index": NotRequired[str],
        "Index-regex": NotRequired[str],
    },
)

_DictSpecWindowOnly = TypedDict(
    "_DictSpecWindowOnly",
    {
        "FrameworkId": NotRequired[str],
        "FrameworkId-regex": NotRequired[str],
        "ProcessName": NotRequired[str],
        "ProcessName-regex": NotRequired[str],
    },
)


class DictSpecWindow(_DictSpecUiaCommon, _DictSpecWindowOnly):
    """Top-level window selector layer; unlike DictSpecUia, it has no Depth."""

    pass


class DictSpecUia(_DictSpecUiaCommon):
    # If Depth is undefined, it means Depth is 1 and therefore searching direct children.
    Depth: NotRequired[str]


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


class DictSpecImage(TypedDict):
    FileName: str
    Grayscale: Literal["true", "false"]
    Confidence: str
    Index: NotRequired[str]


# Selector
class _SelectorBase(TypedDict):
    window: DictSpecWindow


class SelectorWindow(_SelectorBase):
    category: NotRequired[None]


class SelectorUia(_SelectorBase):
    category: Literal["uia"]
    specification: list[DictSpecUia]


class SelectorHtml(_SelectorBase):
    category: Literal["html"]
    specification: list[DictSpecHtml]


class SelectorImage(_SelectorBase):
    category: Literal["image"]
    # Image has only one layer but use list to compatible with others.
    specification: list[DictSpecImage]


type Selector = SelectorWindow | SelectorUia | SelectorHtml | SelectorImage


class DictElementTreeItem(TypedDict):
    id: int
    title: str
    attributes: DictElementTreeUiaAttr | DictSpecHtmlOriginal
    # Quoted forward references
    children: NotRequired[list["DictElementTreeItem"]]


# Dictionary for UI Anaylyzer.
class DictUiAnalyzerIndicateResult(TypedDict):
    selector: Selector
    attributes: DictUiaSecondaryAttr | DictHtmlSecondaryAttr | DictImageAttr
    preview: NotRequired[str]
    recommendedWindow: NotRequired[DictSpecWindow]
    recommendedSpecification: NotRequired[list[DictSpecUia] | list[DictSpecHtml]]


if __name__ == "__main__":
    ...
