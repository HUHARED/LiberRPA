# FileName: _UiAutomation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Exception import UiElementNotFoundError, UiSelectorError
from liberrpa.UI._UiDict import (
    DictUiaPrimaryAttrBasic,
    DictUiaSecondaryAttr,
    DictUiaAttr,
    DictSpecWindow,
    DictSpecUia,
)

import uiautomation
import psutil
import json
import re
from copy import deepcopy
from typing import cast, TypedDict

DICT_CONTROL_TYPE_NUM: dict[str, int] = {
    "AppBarControl": 50040,
    "ButtonControl": 50000,
    "CalendarControl": 50001,
    "CheckBoxControl": 50002,
    "ComboBoxControl": 50003,
    "CustomControl": 50025,
    "DataGridControl": 50028,
    "DataItemControl": 50029,
    "DocumentControl": 50030,
    "EditControl": 50004,
    "GroupControl": 50026,
    "HeaderControl": 50034,
    "HeaderItemControl": 50035,
    "HyperlinkControl": 50005,
    "ImageControl": 50006,
    "ListControl": 50008,
    "ListItemControl": 50007,
    "MenuBarControl": 50010,
    "MenuControl": 50009,
    "MenuItemControl": 50011,
    "PaneControl": 50033,
    "ProgressBarControl": 50012,
    "RadioButtonControl": 50013,
    "ScrollBarControl": 50014,
    "SemanticZoomControl": 50039,
    "SeparatorControl": 50038,
    "SliderControl": 50015,
    "SpinnerControl": 50016,
    "SplitButtonControl": 50031,
    "StatusBarControl": 50017,
    "TabControl": 50018,
    "TabItemControl": 50019,
    "TableControl": 50036,
    "TextControl": 50020,
    "ThumbControl": 50027,
    "TitleBarControl": 50037,
    "ToolBarControl": 50021,
    "ToolTipControl": 50022,
    "TreeControl": 50023,
    "TreeItemControl": 50024,
    "WindowControl": 50032,
}

_TUPLE_PRIMARY_ATTR = (
    "FrameworkId",
    "ControlTypeName",
    "Name",
    "AcceleratorKey",
    "AccessKey",
    "AriaProperties",
    "AriaRole",
    "ClassName",
    "HelpText",
)


_TUPLE_SECONDARY_ATTR = (
    "ControlType",
    "AutomationId",
    "Culture",
    "HasKeyboardFocus",
    "IsContentElement",
    "IsControlElement",
    "IsDataValidForForm",
    "IsEnabled",
    "IsKeyboardFocusable",
    "IsOffscreen",
    "IsPassword",
    "IsRequiredForForm",
    "ItemStatus",
    "ItemType",
    "LocalizedControlType",
    "NativeWindowHandle",
    "Orientation",
    "ProcessId",
    "ProviderDescription",
)


def _convert_value_to_str(dictToConvert: dict[str, str | int]) -> dict[str, str]:
    # Convert all values to string.
    dictReturn: dict[str, str] = {}
    for strKeyName in dictToConvert.keys():
        if not isinstance(dictToConvert[strKeyName], str):
            # convert non-str value to str.
            dictReturn[strKeyName] = json.dumps(dictToConvert[strKeyName])  # Use json for show escape characters.
        else:
            dictReturn[strKeyName] = str(dictToConvert[strKeyName])

    return dictReturn


def get_control_primary_attr(control: uiautomation.Control) -> DictUiaPrimaryAttrBasic:
    dictTemp: dict[str, str | int] = {}
    try:
        # Try to get "ProcessName".
        dictTemp["ProcessName"] = psutil.Process(control.ProcessId).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        raise ValueError("The target process is no longer available or cannot be accessed.")

    # Find primary attributes.
    for strAttrName in _TUPLE_PRIMARY_ATTR:
        try:
            # Using getattr to fetch the attribute from the control.
            value = getattr(control, strAttrName)
            if value == "" or value is None:
                # If the attribute is empty string or null, ignore it.
                continue

            if strAttrName.startswith("Is"):
                # Convert some 0,1 attributes to Boolean.
                value = bool(value)
            dictTemp[strAttrName] = value

        except Exception as e:
            # If some value doesn't be got, just ignore.
            Log.error(f"Error fetching {strAttrName}: {e}")

    return cast(DictUiaPrimaryAttrBasic, _convert_value_to_str(dictTemp))


def get_control_secondary_attr(control: uiautomation.Control) -> DictUiaSecondaryAttr:
    dictTemp: dict[str, str | int] = {}
    for strAttrName in _TUPLE_SECONDARY_ATTR:
        try:
            value = getattr(control, strAttrName)
            if value == "" or value is None:
                continue
            if strAttrName.startswith("Is"):
                value = bool(value)
            # Add the prefix "secondary-" for all seconary attributes.
            dictTemp["secondary-" + strAttrName] = value

        except Exception as e:
            Log.error(f"Error fetching {strAttrName}: {e}")

    # Add coordinate and size.
    dictTemp["secondary-x"] = control.BoundingRectangle.left
    dictTemp["secondary-y"] = control.BoundingRectangle.top
    dictTemp["secondary-width"] = control.BoundingRectangle.width()
    dictTemp["secondary-height"] = control.BoundingRectangle.height()

    return cast(DictUiaSecondaryAttr, _convert_value_to_str(dictTemp))


def get_control_attr(control: uiautomation.Control) -> DictUiaAttr:
    return {**get_control_primary_attr(control=control), **get_control_secondary_attr(control=control)}


def get_top_control(selectorWindowPart: DictSpecWindow) -> uiautomation.Control:

    # Create a copy to pop later, so it will not affect the original selector.
    selectorWindowPart = deepcopy(selectorWindowPart)

    # Start the search from the root control.
    controlRoot = uiautomation.GetRootControl()
    # print("controlRoot", controlRoot)
    controlTarget: uiautomation.Control | None = None

    # May have multiple top controls that have same attributes. So save Index to a variable to check it later.

    strTemp = selectorWindowPart.pop("Index", None)
    intIndex = int(strTemp) if strTemp else None
    strIndexRegex = selectorWindowPart.pop("Index-regex", None)

    intFoundMatchedCount = 0

    controlChild = controlRoot.GetFirstChildControl()
    # print("controlChild", controlChild)

    while controlChild:
        dictPrimaryAttrTemp: DictUiaPrimaryAttrBasic = get_control_primary_attr(control=controlChild)
        boolAttrSame = True

        # Check all attributes in selector. (index popped)
        for strKeyName in selectorWindowPart:
            if not strKeyName.endswith("-regex"):
                # if the attribute is not exists or not equal with selector, stop the inner loop.
                if (dictPrimaryAttrTemp.get(strKeyName) is None) or (
                    dictPrimaryAttrTemp[strKeyName] != selectorWindowPart[strKeyName]
                ):
                    boolAttrSame = False
                    break
            else:
                # the regex not match.
                strOriginalKeyName = strKeyName.removesuffix("-regex")
                if (dictPrimaryAttrTemp.get(strOriginalKeyName) is None) or (
                    not re.fullmatch(
                        pattern=selectorWindowPart[strKeyName],
                        string=dictPrimaryAttrTemp[strOriginalKeyName],
                    )
                ):
                    boolAttrSame = False
                    break

        if not boolAttrSame:
            # If the attributes are not all same, check the next.
            controlChild = controlChild.GetNextSiblingControl()
            continue
        else:
            # If the index matches with selector's Index or Index-regex, stop the outer loop, otherwise continue to check the next.

            if intIndex is None and strIndexRegex is None:
                # # The selector has no Index or Index-regex, not need to compare.
                controlTarget = controlChild
                break

            elif intIndex is None and strIndexRegex is not None:
                # Just have Index-regex
                if re.fullmatch(pattern=strIndexRegex, string=str(intFoundMatchedCount)):
                    controlTarget = controlChild
                    break
                else:
                    # Not matched, increase the count, check the next.
                    intFoundMatchedCount += 1
                    controlChild = controlChild.GetNextSiblingControl()
                    continue
            # Just have Index
            elif intIndex is not None and strIndexRegex is None:
                if intIndex == intFoundMatchedCount:
                    controlTarget = controlChild
                    break
                else:
                    # Not matched, increase the count, check the next.
                    intFoundMatchedCount += 1
                    controlChild = controlChild.GetNextSiblingControl()
                    continue
            else:
                # Have Index and Index-regex, it is wrong.
                raise ValueError("Index and Index-regex should not appear in selector together.")

    if controlTarget is None:
        raise UiElementNotFoundError(f"Not found window by the selector: {selectorWindowPart}")

    return controlTarget


class DictUiaBuiltinSearchKwargs(TypedDict, total=False):
    searchDepth: int
    foundIndex: int
    RegexName: str
    Name: str
    ClassName: str
    # uiautomation supports AutomationId, but LiberRPA currently treats it as a secondary attribute instead of a selector field because it is often missing in tested applications.
    # AutomationId: str
    ControlType: int


def _get_uia_builtin_search_kwargs(
    dictSelectorTemp: DictSpecUia,
    searchDepth: int,
    foundIndex: int,
) -> DictUiaBuiltinSearchKwargs:
    """
    Build search kwargs for uiautomation.Control() without changing LiberRPA selector semantics.

    Only exact fields are pushed down to uiautomation. Regex fields are still checked by LiberRPA
    because uiautomation.RegexName uses re.match while LiberRPA selector regex uses re.fullmatch.

    By default, search is limited to controls with a non-empty Name because Name is the most
    useful built-in UIA search key in current LiberRPA selector design.
    """
    dictSearchKwargs: DictUiaBuiltinSearchKwargs = {
        "searchDepth": searchDepth,
        "foundIndex": foundIndex,
        # Only search controls with a non-empty Name, unless an exact non-empty Name is pushed down.
        "RegexName": ".+",
    }

    strName = dictSelectorTemp.get("Name")
    if isinstance(strName, str) and strName != "":
        # Name and RegexName should not be used together.
        dictSearchKwargs.pop("RegexName", None)
        dictSearchKwargs["Name"] = strName

    strClassName = dictSelectorTemp.get("ClassName")
    if isinstance(strClassName, str):
        dictSearchKwargs["ClassName"] = strClassName

    strControlTypeName = dictSelectorTemp.get("ControlTypeName")
    if isinstance(strControlTypeName, str):
        intControlType = DICT_CONTROL_TYPE_NUM.get(strControlTypeName)
        if intControlType is None:
            raise UiSelectorError(f"Unsupported ControlTypeName: {strControlTypeName!r}.")

        dictSearchKwargs["ControlType"] = intControlType

    return dictSearchKwargs


def get_child_control_by_selector(
    selectorUiaPart: list[DictSpecUia], controlTop: uiautomation.Control
) -> uiautomation.Control:
    # Create a copy to pop later, so it will not affect the original selector.
    selectorUiaPart = deepcopy(selectorUiaPart)

    controlAnchor = controlTop

    # Go to the next deeper layer by each loop.
    for i in range(0, len(selectorUiaPart), 1):
        dictSelectorTemp: DictSpecUia = selectorUiaPart[i]

        # May have multiple top controls that have same attributes. So save Index to a variable to check it later.

        strTemp = dictSelectorTemp.pop("Index", None)
        intIndex = int(strTemp) if strTemp else None
        strIndexRegex = dictSelectorTemp.pop("Index-regex", None)

        # If the layer's attributes have no "Depth", means it's a direct child control, set searchDepth to 1.
        strTemp = dictSelectorTemp.pop("Depth", None)
        intSearchDepth = int(strTemp) if strTemp else 1

        intFoundMatchedCount = 0

        intFoundIndex = 1

        while True:
            try:
                dictSearchKwargs = _get_uia_builtin_search_kwargs(
                    dictSelectorTemp=dictSelectorTemp,
                    searchDepth=intSearchDepth,
                    foundIndex=intFoundIndex,
                )

                controlFound = controlAnchor.Control(**dictSearchKwargs)
                # Because control find process seems asynchronous, use an assign to wait it done or timeout.
                _ = str(controlFound)

            except UiSelectorError:
                raise

            except Exception as e:
                Log.error(e)
                controlFound = None

            if controlFound is None:
                raise UiElementNotFoundError(f"Not found an uia element by the selector: {selectorUiaPart}")

            dictPrimaryAttrTemp: DictUiaPrimaryAttrBasic = get_control_primary_attr(control=controlFound)
            boolAttrSame = True

            # Check all attributes in dictCurrentLayer. (index and depth popped)
            for strKeyName in dictSelectorTemp:
                if not strKeyName.endswith("-regex"):
                    if (dictPrimaryAttrTemp.get(strKeyName) is None) or (
                        dictPrimaryAttrTemp[strKeyName] != dictSelectorTemp[strKeyName]
                    ):
                        boolAttrSame = False
                        break
                else:
                    strOriginalKeyName = strKeyName.removesuffix("-regex")
                    if (dictPrimaryAttrTemp.get(strOriginalKeyName) is None) or (
                        not re.fullmatch(
                            pattern=dictSelectorTemp[strKeyName],
                            string=dictPrimaryAttrTemp[strOriginalKeyName],
                        )
                    ):
                        boolAttrSame = False
                        break

            if not boolAttrSame:
                # If the attributes are not all same, check the next.
                intFoundIndex += 1
                continue
            else:
                if intIndex is None and strIndexRegex is None:
                    # # The selector has no Index or Index-regex, not need to compare.
                    controlAnchor = controlFound
                    break
                elif intIndex is None and strIndexRegex is not None:
                    # Just have Index-regex
                    if re.fullmatch(pattern=strIndexRegex, string=str(intFoundMatchedCount)):
                        controlAnchor = controlFound
                        break
                    else:
                        # Not matched, increase the count, check the next.
                        intFoundMatchedCount += 1
                        intFoundIndex += 1
                        continue
                elif intIndex is not None and strIndexRegex is None:
                    if intIndex == intFoundMatchedCount:
                        controlAnchor = controlFound
                        break
                    else:
                        # Not matched, increase the count, check the next.
                        intFoundMatchedCount += 1
                        intFoundIndex += 1
                        continue
                else:
                    # Have Index and Index-regex, it is wrong.
                    raise ValueError("Index and Index-regex should not appear in selector together.")

    return controlAnchor


def activate_control_window(control: uiautomation.Control) -> None:
    with uiautomation.UIAutomationInitializerInThread():
        controlTop = control.GetTopLevelControl()
        if controlTop is None:
            raise UiElementNotFoundError("Failed to get top-level control.")

        intHandle = controlTop.NativeWindowHandle
        pattern = cast(
            uiautomation.WindowPattern | None,
            controlTop.GetPattern(uiautomation.PatternId.WindowPattern),
        )
        if pattern is not None:
            intCurrentState = pattern.WindowVisualState
            # 0: normal; 1: maximized; 2: minimized
            if intCurrentState == 2:
                uiautomation.ShowWindow(handle=intHandle, cmdShow=uiautomation.SW.Restore)
        uiautomation.SetForegroundWindow(handle=intHandle)


def get_children_control_recursive(control: uiautomation.Control) -> list[uiautomation.Control]:
    listReturn: list[uiautomation.Control] = []
    for controlChild in control.GetChildren():
        strNameTemp = getattr(controlChild, "Name", None)
        if strNameTemp is None or strNameTemp == "":
            # If the control has no "Name", get its children control.
            listTemp = get_children_control_recursive(control=controlChild)
            listReturn = [*listReturn, *listTemp]
        else:
            listReturn.append(controlChild)

    return listReturn


if __name__ == "__main__":
    ...
