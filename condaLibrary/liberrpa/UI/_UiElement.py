# FileName: _UiElement.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.UI._UiAutomation import (
    DICT_CONTROL_TYPE_NUM,
    get_top_control,
    get_control_attr,
    get_control_primary_attr,
    activate_control_window,
    get_child_control_by_selector,
)
from liberrpa.UI._CommonValue import boolHighlightUi
from liberrpa.Common._Exception import UiElementNotFoundError
from liberrpa.Common._TypedValue import ExecutionMode
from liberrpa.UI._UiDict import (
    DictSpecWindow,
    DictSpecUia,
    DictSpecUiaOriginalTemp,
    DictSepcImage,
    DictUiaAttr,
    DictHtmlAttr,
    DictImageAttr,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
    SelectorImage,
)
from liberrpa.Basic import delay
import liberrpa.Common._Chrome as _Chrome
from liberrpa.UI._Overlay import create_overlay
from liberrpa.UI._Image import find_image
from liberrpa.UI._SelectorValidation import (
    as_selector_uia,
    as_selector_html,
    as_selector_image,
    validate_selector,
)

import uiautomation
import pyautogui
from time import monotonic, sleep
import threading
from contextlib import contextmanager
from collections.abc import Sequence

from typing import cast


# Set the global variable of uiautomation.
uiautomation.SEARCH_INTERVAL = 1.0
uiautomation.OPERATION_WAIT_TIME = 0
uiautomation.SetGlobalSearchTimeout(10)
Log.verbose(f"Initialize uiautomation in thread: {threading.current_thread().name}")


@contextmanager
def holding_modifier_keys(*, pressCtrl=False, pressShift=False, pressAlt=False, pressWin=False):
    pressedKeys: list[str] = []

    try:
        if pressCtrl:
            pyautogui.keyDown(key="ctrl")
            pressedKeys.append("ctrl")
        if pressAlt:
            pyautogui.keyDown(key="alt")
            pressedKeys.append("alt")
        if pressShift:
            pyautogui.keyDown(key="shift")
            pressedKeys.append("shift")
        if pressWin:
            pyautogui.keyDown(key="win")
            pressedKeys.append("win")

        yield

    finally:
        for key in reversed(pressedKeys):
            pyautogui.keyUp(key=key)


def check_execution_type(executionMode: ExecutionMode) -> None:
    """Invoke by GUI manipulation functions to check mode."""
    listValue = ["simulate", "api"]
    if executionMode not in listValue:
        raise ValueError(f"The argument executionMode({executionMode}) should be one of {listValue}")


def check_set_timeout(timeout: int) -> int:
    """Invoke by GUI manipulation functions to check timeout. If timeout < 3000 (milliseconds), set it to 3000."""
    timeoutMin = 3000
    if timeout < timeoutMin:
        timeout = timeoutMin
        Log.warning(f"The argument 'timeout' should be at least {timeoutMin}, set it.")
    # Synchronize uiautomation's TIME_OUT_SECOND.
    uiautomation.SetGlobalSearchTimeout(timeout / 1000)
    return timeout


def get_control_selector(
    control: uiautomation.Control,
) -> SelectorWindow | SelectorUia:

    listAllLayerControl: list[uiautomation.Control] = []
    listLayersAttr: list[DictSpecUiaOriginalTemp] = []

    # Add all attributes to selector except Index.
    try:
        # Find the element under the cursor
        element = control

        # Depth to its parent which has "Name".
        intToNamedParentDepth: int = 1
        while element is not None:
            # Add the current layer's attributes.
            dictCurrentLayerPrimaryAttr = cast(
                DictSpecUiaOriginalTemp, get_control_primary_attr(control=element)
            )  # "FrameworkId", "ProcessName", "NextLayerDepth" be added later or be deleted.

            # Keep only the layer that contains "Name", and add it to listAllLayerControl for adding Index later.
            if dictCurrentLayerPrimaryAttr.get("Name"):
                dictCurrentLayerPrimaryAttr["NextLayerDepth"] = str(intToNamedParentDepth)

                listLayersAttr.insert(0, dictCurrentLayerPrimaryAttr)
                listAllLayerControl.insert(0, element)

                intToNamedParentDepth = 1
            else:
                intToNamedParentDepth += 1

            # Assign the parent element for next loop.
            element = element.GetParentControl()
            if element is not None and element.ControlTypeName == "PaneControl" and element.ClassName == "#32769":
                """
                This is the desktop layer.
                Move the "NextLayerDepth" of each layer to next layer, renamed as "Depth"
                Add the Desktop control to the start of listAllLayerControl, to calculate Index attribute later.
                Then break out of the loop.
                """
                # Give the Depth to its child(next) layer, which means the maximum depth when finding next layer. Ignore when it's 1.
                # From the last to the second.
                for i in range(len(listLayersAttr) - 1, 0, -1):
                    del listLayersAttr[i]["NextLayerDepth"]
                    temp = listLayersAttr[i - 1].get("NextLayerDepth")
                    if temp and int(temp) > 1:
                        listLayersAttr[i]["Depth"] = temp
                # Delete NextLayerDepth of the window layer. Because it has no previous element in the list, just need to delete NextLayerDepth, didn't need to add Depth.
                del listLayersAttr[0]["NextLayerDepth"]
                # Add the Desktop control for adding Index later.
                listAllLayerControl.insert(0, element)
                break

    except Exception as e:
        Log.error(f"(!!!It should not appear.) Error finding element: {e}")

    """
    Add "Index" to each layer of selector(if needed)
    The attribute "Index" means the order of the current layer element in its parent element's children have same primary attributes. It's not the Control() arguemnt "foundIndex".
    Use the current one(currentControl) to add index into the next one(controlTarget), so the last one doesn't to process.
    """
    for i in range(0, len(listAllLayerControl) - 1, 1):
        controlParent = listAllLayerControl[i]
        controlTarget = listAllLayerControl[i + 1]
        dictTargetLayerAttr = listLayersAttr[i]
        intFoundIndex = 1
        intIndex = 0

        # Loop to find, until found it or time out.
        while True:
            # "ClassName" may not exist.
            ClassName = dictTargetLayerAttr.get("ClassName")

            # If the layer's attributes have no "Depth", means it's a direct child control, set searchDepth to 1.
            temp = dictTargetLayerAttr.get("Depth")
            if temp is None:
                intSearchDepth = 1
            else:
                intSearchDepth = int(temp)

            # Find target in the current control.
            try:
                if ClassName:
                    controlFound = controlParent.Control(
                        searchDepth=intSearchDepth,
                        foundIndex=intFoundIndex,
                        ControlType=DICT_CONTROL_TYPE_NUM.get(dictTargetLayerAttr["ControlTypeName"]),
                        Name=dictTargetLayerAttr["Name"],
                        ClassName=ClassName,
                    )
                else:
                    controlFound = controlParent.Control(
                        searchDepth=intSearchDepth,
                        foundIndex=intFoundIndex,
                        ControlType=DICT_CONTROL_TYPE_NUM.get(dictTargetLayerAttr["ControlTypeName"]),
                        Name=dictTargetLayerAttr["Name"],
                    )
                # Because control find process seems asynchronous, use an assign to wait it done or timeout,.
                _ = str(controlFound)
            except Exception as e:
                Log.error(f"Error when searching control: {e}")
                controlFound = None

            if controlFound is None:
                raise UiElementNotFoundError("(!!!It should not appear.) Not found element when adding Index.")

            """
            Check whether other primary attributes are same.
            If one of them is different, continue to find next.
            Note that "ProcessName" is not a direct attribute, replace it by "ProcessId".
            Name and ClassName, ControlType were checked in previous.
            """
            boolOtherPrimaryAttrSame = True
            for attr in [
                "FrameworkId",
                "AcceleratorKey",
                "AccessKey",
                "AriaProperties",
                "AriaRole",
                "HelpText",
                "ProcessId",
            ]:
                if getattr(controlFound, attr) != getattr(controlTarget, attr):
                    boolOtherPrimaryAttrSame = False
                    break
            if not boolOtherPrimaryAttrSame:
                intFoundIndex += 1
                continue

            # If all primiary attributes are same, check whether they are the same one. If they are the same one, assign the Index and break out theloop. Else increase intIndex to find next.
            if uiautomation.ControlsAreSame(controlFound, controlTarget):
                # There is no need to add "Index" when intIndex == 0, for keeping the selector concise.
                if intIndex > 0:
                    dictTargetLayerAttr["Index"] = str(intIndex)
                break
            else:
                intFoundIndex += 1
                intIndex += 1
                continue

    # Only the top layer need the attributes "ProcessName" and "FrameworkId", to make the selector more concise.
    for i in range(1, len(listLayersAttr), 1):
        del listLayersAttr[i]["ProcessName"]
        if listLayersAttr[i].get("FrameworkId") is not None:
            del listLayersAttr[i]["FrameworkId"]

    if len(listLayersAttr) == 1:
        # If it's a window control(just one layer)
        # SelectorWindowOriginal, treat it as SelectorWindow for use later.
        return {"window": cast(DictSpecWindow, listLayersAttr[0])}
    else:
        # SelectorUiaOriginal, treat it as SelectorUia for use later.
        # Use Sequence to convert the type for Pylance
        return {
            "window": cast(DictSpecWindow, listLayersAttr[0]),
            "category": "uia",
            "specification": list(cast(Sequence[DictSpecUia], listLayersAttr[1:])),
        }


def get_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
) -> tuple[uiautomation.Control, DictUiaAttr] | tuple[None, DictHtmlAttr] | tuple[None, DictImageAttr]:
    """Get a control or html and its attributes dictionary by selector, so the following code can use them."""
    global boolHighlightUi

    validate_selector(selector=selector)

    with uiautomation.UIAutomationInitializerInThread():
        # Find and activate top control.
        controlTop = get_top_control(selectorWindowPart=selector["window"])
        activate_control_window(control=controlTop)

        # A window element.
        if selector.get("category") is None:
            Log.verbose("It's a window.")
            return (controlTop, get_control_attr(control=controlTop))

        if selector.get("specification") is None:
            raise ValueError(f"Not find 'specification' value in the selector: {selector}")

        # An uia or html element

        match selector.get("category"):
            case "uia":
                controlTemp = get_child_control_by_selector(
                    selectorUiaPart=as_selector_uia(selector=selector)["specification"], controlTop=controlTop
                )
                if boolHighlightUi:
                    create_overlay(
                        controlTemp.BoundingRectangle.left,
                        controlTemp.BoundingRectangle.top,
                        controlTemp.BoundingRectangle.width(),
                        controlTemp.BoundingRectangle.height(),
                        color="red",
                        duration=200,
                        label=controlTemp.ControlTypeName,
                    )
                return (controlTemp, get_control_attr(control=controlTemp))
            case "html":
                # Only Chrome now. If has other browser, use ProcessName to call the browser extension.

                # The target window has been activated. Call the Chrome module to get the attributes.
                dictAttr: DictHtmlAttr = _Chrome.get_element_attr_by_selector(
                    htmlSelector=as_selector_html(selector=selector)["specification"]
                )

                if boolHighlightUi:
                    tagName = dictAttr.get("tagName")
                    if not isinstance(tagName, str) or not tagName:
                        raise UiElementNotFoundError(f"HTML element has no valid tagName. attr: {dictAttr}")

                    create_overlay(
                        int(dictAttr["secondary-x"]),
                        int(dictAttr["secondary-y"]),
                        int(dictAttr["secondary-width"]),
                        int(dictAttr["secondary-height"]),
                        color="red",
                        duration=200,
                        label=tagName,
                    )
                return (None, dictAttr)
            case "image":
                selectorTemp: SelectorImage = as_selector_image(selector)
                if len(selectorTemp["specification"]) != 1:
                    raise ValueError(
                        f"It should have only one dictionary in 'specification', but it has {len(selectorTemp['specification'])}"
                    )
                imageSelector: DictSepcImage = selectorTemp["specification"][0]

                # delay 100 ms before find_image due to the window may just activate.
                sleep(0.1)

                listDictImageAttr = find_image(
                    fileNameOrPath=imageSelector["FileName"],
                    region=(
                        controlTop.BoundingRectangle.left,
                        controlTop.BoundingRectangle.top,
                        controlTop.BoundingRectangle.width(),
                        controlTop.BoundingRectangle.height(),
                    ),
                    confidence=float(imageSelector["Confidence"]),
                    grayscale=True if imageSelector["Grayscale"] == "true" else False,
                    # If have no Index or Index = "0", limit should be 1, else limit should be Index+1, due to All Index in LiberRPA selector start from 0.
                    limit=int(imageSelector.get("Index", "0")) + 1,
                    moveFile=True,
                    inScreenshotFolder=True,
                )
                # The list's length has limited by Index, but it may not find enough image(0 or less than Index+1), so check it.
                if len(listDictImageAttr) < int(imageSelector.get("Index", "0")) + 1:
                    raise UiElementNotFoundError(f"Not Found image element. selector's specification: {imageSelector}")
                # length = Index+1, return the last one.

                if boolHighlightUi:
                    create_overlay(
                        int(listDictImageAttr[-1]["secondary-x"]),
                        int(listDictImageAttr[-1]["secondary-y"]),
                        int(listDictImageAttr[-1]["secondary-width"]),
                        int(listDictImageAttr[-1]["secondary-height"]),
                        color="red",
                        duration=200,
                        label="Image",
                    )
                return (None, listDictImageAttr[-1])

            case _:
                raise ValueError(f"Not find right 'category'(uia/html/image) value in the selector: {selector}")


def get_element_with_pre_delay(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
    preExecutionDelay: int = 300,
) -> tuple[uiautomation.Control, DictUiaAttr] | tuple[None, DictHtmlAttr] | tuple[None, DictImageAttr]:
    """Calculate the time-consuming of get element, if it's more than preExecutionDelay, didn't need to delay."""

    timeStart = monotonic()
    temp = get_element(selector=selector)
    # log.debug(temp)
    timeUsed = (monotonic() - timeStart) * 1000
    if timeUsed < preExecutionDelay:
        delay(preExecutionDelay - int(timeUsed))

    return temp


def activate_element_window(selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage) -> None:

    validate_selector(selector=selector)

    with uiautomation.UIAutomationInitializerInThread():
        # Find and activate top control.
        controlTop = get_top_control(selectorWindowPart=selector["window"])
        activate_control_window(control=controlTop)


if __name__ == "__main__":
    ...
