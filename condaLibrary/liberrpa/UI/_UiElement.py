# FileName: _UiElement.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.UI._UiAutomation import (
    get_top_control,
    get_control_attr,
    get_control_primary_attr,
    activate_control_window,
    get_child_control_by_selector,
)
import liberrpa.UI._CommonValue as _CommonValue
from liberrpa.Common._Exception import UiElementNotFoundError, UiOperationError
from liberrpa.Common._TypedValue import ExecutionMode
from liberrpa.UI._UiDict import (
    DictSpecImage,
    DictUiaAttr,
    DictHtmlAttr,
    DictImageAttr,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
    SelectorImage,
    Selector,
)
from liberrpa.Basic import delay
import liberrpa.Common._Chrome as _Chrome
from liberrpa.UI._Overlay import create_overlay
from liberrpa.UI._Image import find_image
from liberrpa.UI._SelectorValidation import (
    ensure_selector_window,
    ensure_selector_uia,
    ensure_selector_html,
    ensure_selector_image,
    validate_selector,
)

import uiautomation
import pyautogui
from time import monotonic, sleep
import threading
from contextlib import contextmanager
from collections.abc import Generator
from dataclasses import dataclass
from typing import overload


# Set the global variable of uiautomation.
uiautomation.SEARCH_INTERVAL = 1.0
uiautomation.OPERATION_WAIT_TIME = 0
uiautomation.SetGlobalSearchTimeout(10)
uiautomation.Logger.SetLogFile("")
Log.verbose(f"Initialize uiautomation in thread: {threading.current_thread().name}")


@contextmanager
def holding_modifier_keys(
    *,
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
) -> Generator[None]:
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
        raise ValueError(
            f"The argument executionMode({executionMode}) should be one of {listValue}"
        )


def check_set_timeout(timeout: int) -> int:
    """Invoke by GUI manipulation functions to check timeout. If timeout < 3000 (milliseconds), set it to 3000."""

    if type(timeout) is not int:
        raise ValueError("timeout must be an integer number of milliseconds.")

    if timeout < _CommonValue.INT_TIMEOUT_MIN:
        timeout = _CommonValue.INT_TIMEOUT_MIN
        Log.warning(
            f"The argument 'timeout' should be at least {_CommonValue.INT_TIMEOUT_MIN}; "
            f"using {_CommonValue.INT_TIMEOUT_MIN}."
        )
    # Synchronize uiautomation's TIME_OUT_SECOND.
    uiautomation.SetGlobalSearchTimeout(timeout / 1000)
    return timeout


@dataclass
class _UiaSelectorLayerDraft:
    control: uiautomation.Control
    attributes: dict[str, str]
    rectangle: tuple[int, int, int, int] | None = None
    depthFromParent: int = 1
    index: int | None = None


def _copy_control_primary_attr(control: uiautomation.Control) -> dict[str, str]:
    """Copy a TypedDict to a normal homogeneous dictionary."""

    dictResult: dict[str, str] = {}
    for strKey, value in get_control_primary_attr(control=control).items():
        if not isinstance(value, str):
            raise UiOperationError(
                f"Unexpected non-string UIA primary attribute {strKey!r}: {value!r}."
            )
        dictResult[strKey] = value

    return dictResult


def _control_matches_attributes(
    control: uiautomation.Control,
    dictExpected: dict[str, str],
) -> bool:
    dictActual = _copy_control_primary_attr(control=control)
    return all(
        dictActual.get(strKey) == strValue for strKey, strValue in dictExpected.items()
    )


def _try_get_control_rectangle(
    control: uiautomation.Control,
) -> tuple[int, int, int, int] | None:
    try:
        rectangle = control.BoundingRectangle
    except Exception:
        return None

    return (
        rectangle.left,
        rectangle.top,
        rectangle.width(),
        rectangle.height(),
    )


def _rectangles_are_close(
    rectangleLeft: tuple[int, int, int, int],
    rectangleRight: tuple[int, int, int, int],
    tolerance: int = 1,
) -> bool:
    return all(
        abs(intLeft - intRight) <= tolerance
        for intLeft, intRight in zip(rectangleLeft, rectangleRight, strict=True)
    )


def _get_layer_index(
    controlParent: uiautomation.Control,
    layer: _UiaSelectorLayerDraft,
) -> tuple[int | None, uiautomation.Control]:
    """Return the target index and matching control from the current UIA tree."""

    intMatchedIndex = 0
    listRectangleFallback: list[tuple[int, uiautomation.Control]] = []

    try:
        for controlFound, _intDepth in uiautomation.WalkControl(
            control=controlParent,
            maxDepth=layer.depthFromParent,
        ):
            try:
                # Keep the same traversal order and maximum-depth semantics used by uiautomation.Control().
                if controlFound.ControlTypeName != layer.attributes["ControlTypeName"]:
                    continue
                if (
                    "Name" in layer.attributes
                    and controlFound.Name != layer.attributes["Name"]
                ):
                    continue
                if (
                    "ClassName" in layer.attributes
                    and controlFound.ClassName != layer.attributes["ClassName"]
                ):
                    continue
                if not _control_matches_attributes(
                    control=controlFound,
                    dictExpected=layer.attributes,
                ):
                    continue
            except Exception:
                # A control that becomes unavailable during enumeration cannot be used to build this layer.
                continue

            try:
                boolSameControl = uiautomation.ControlsAreSame(
                    controlFound, layer.control
                )
            except Exception:
                boolSameControl = False

            if boolSameControl:
                # Index 0 is the default and is omitted to keep the selector concise.
                return (
                    intMatchedIndex if intMatchedIndex > 0 else None,
                    controlFound,
                )

            tupleFoundRectangle = _try_get_control_rectangle(control=controlFound)
            if (
                layer.rectangle is not None
                and tupleFoundRectangle is not None
                and _rectangles_are_close(
                    rectangleLeft=tupleFoundRectangle,
                    rectangleRight=layer.rectangle,
                )
            ):
                listRectangleFallback.append((intMatchedIndex, controlFound))

            intMatchedIndex += 1

    except Exception as e:
        raise UiElementNotFoundError(
            "Failed to traverse the current UIA tree while selector index information was being built."
        ) from e

    if len(listRectangleFallback) == 1:
        intFallbackIndex, controlFallback = listRectangleFallback[0]
        Log.debug({
            "message": "Use UIA rectangle fallback while building selector.",
            "attributes": layer.attributes,
            "rectangle": layer.rectangle,
            "index": intFallbackIndex,
        })
        return (
            intFallbackIndex if intFallbackIndex > 0 else None,
            controlFallback,
        )

    if len(listRectangleFallback) > 1:
        raise UiElementNotFoundError(
            f"The selected UI element matched multiple controls at the same rectangle while selector index information was being built. attributes={layer.attributes!r}, rectangle={layer.rectangle!r}."
        )

    raise UiElementNotFoundError(
        f"The selected UI element could not be identified in the current UIA tree while selector index information was being built. attributes={layer.attributes!r}, rectangle={layer.rectangle!r}."
    )


def _get_control_path(control: uiautomation.Control) -> list[uiautomation.Control]:
    """Return the controls from the desktop's direct child through control."""

    controlRoot = uiautomation.GetRootControl()
    listPath = [control]
    controlCurrent = control

    while True:
        controlParent = controlCurrent.GetParentControl()
        if controlParent is None:
            raise UiElementNotFoundError(
                "Failed to reach the desktop root while building the target UI element's selector."
            )

        if uiautomation.ControlsAreSame(controlParent, controlRoot):
            return listPath

        listPath.insert(0, controlParent)
        controlCurrent = controlParent


def get_control_window(control: uiautomation.Control) -> uiautomation.Control:
    """Return the desktop-root child that contains control."""

    return _get_control_path(control=control)[0]


def get_control_selector(
    control: uiautomation.Control,
    *,
    targetRectangle: tuple[int, int, int, int] | None = None,
) -> SelectorWindow | SelectorUia:
    """Build a selector for the exact control, including an unnamed target."""

    try:
        listControlPath = _get_control_path(control=control)
        listLayers: list[_UiaSelectorLayerDraft] = []
        intPreviousIncludedPathIndex = -1

        for intPathIndex, controlCurrent in enumerate(listControlPath):
            boolIsWindowLayer = intPathIndex == 0
            boolIsTarget = intPathIndex == len(listControlPath) - 1
            dictAttributes = _copy_control_primary_attr(control=controlCurrent)

            # Always keep the window and exact target. Unnamed intermediate containers remain omitted; Depth preserves the skipped distance.
            if not (boolIsWindowLayer or boolIsTarget or "Name" in dictAttributes):
                continue

            if not boolIsWindowLayer:
                dictAttributes.pop("FrameworkId", None)
                dictAttributes.pop("ProcessName", None)

            intDepthFromParent = (
                1 if boolIsWindowLayer else intPathIndex - intPreviousIncludedPathIndex
            )
            tupleRectangle = (
                targetRectangle
                if boolIsTarget and targetRectangle is not None
                else _try_get_control_rectangle(control=controlCurrent)
            )
            listLayers.append(
                _UiaSelectorLayerDraft(
                    control=controlCurrent,
                    attributes=dictAttributes,
                    rectangle=tupleRectangle,
                    depthFromParent=intDepthFromParent,
                )
            )
            intPreviousIncludedPathIndex = intPathIndex

        if not listLayers:
            raise UiOperationError(
                "No selector layer could be built for the target control."
            )

        controlParent = uiautomation.GetRootControl()
        for layer in listLayers:
            layer.index, controlParent = _get_layer_index(
                controlParent=controlParent, layer=layer
            )

        listSelectorLayers: list[dict[str, str]] = []
        for intLayerIndex, layer in enumerate(listLayers):
            dictLayer = layer.attributes.copy()

            if intLayerIndex > 0 and layer.depthFromParent > 1:
                dictLayer["Depth"] = str(layer.depthFromParent)
            if layer.index is not None:
                dictLayer["Index"] = str(layer.index)

            listSelectorLayers.append(dictLayer)

        if len(listSelectorLayers) == 1:
            return ensure_selector_window({"window": listSelectorLayers[0]})

        return ensure_selector_uia({
            "window": listSelectorLayers[0],
            "category": "uia",
            "specification": listSelectorLayers[1:],
        })

    except (UiElementNotFoundError, UiOperationError):
        raise
    except Exception as e:
        raise UiOperationError("Unexpected error while building the UI selector.") from e


@overload
def get_element(
    selector: SelectorWindow | SelectorUia,
) -> tuple[uiautomation.Control, DictUiaAttr]: ...


@overload
def get_element(selector: SelectorHtml) -> tuple[None, DictHtmlAttr]: ...


@overload
def get_element(selector: SelectorImage) -> tuple[None, DictImageAttr]: ...


def get_element(
    selector: Selector,
) -> (
    tuple[uiautomation.Control, DictUiaAttr]
    | tuple[None, DictHtmlAttr]
    | tuple[None, DictImageAttr]
):
    """Get a control or html and its attributes dictionary by selector, so the following code can use them."""

    validate_selector(selector=selector)

    with uiautomation.UIAutomationInitializerInThread():
        # Find and activate top control.
        controlTop = get_top_control(selectorWindowPart=selector["window"])

        # Ensure the target window is visible.
        activate_control_window(control=controlTop)

        # A window element.
        if selector.get("category") is None:
            Log.verbose("It's a window.")
            return (controlTop, get_control_attr(control=controlTop))

        if selector.get("specification") is None:
            raise ValueError(
                f"Could not find 'specification' value in the selector: {selector}"
            )

        # An uia or html element

        match selector.get("category"):
            case "uia":
                controlTemp = get_child_control_by_selector(
                    selectorUiaPart=ensure_selector_uia(selector)["specification"],
                    controlTop=controlTop,
                )
                if _CommonValue.boolHighlightUi:
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
                    htmlSelector=ensure_selector_html(selector)["specification"]
                )

                if _CommonValue.boolHighlightUi:
                    tagName = dictAttr.get("tagName")
                    if not isinstance(tagName, str) or not tagName:
                        raise UiElementNotFoundError(
                            f"HTML element has no valid tagName. attr: {dictAttr}"
                        )

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
                selectorTemp: SelectorImage = ensure_selector_image(selector)
                if len(selectorTemp["specification"]) != 1:
                    raise ValueError(
                        f"It should have only one dictionary in 'specification', but it has {len(selectorTemp['specification'])}"
                    )
                imageSelector: DictSpecImage = selectorTemp["specification"][0]

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
                    raise UiElementNotFoundError(
                        f"Not Found image element. selector's specification: {imageSelector}"
                    )
                # length = Index+1, return the last one.

                if _CommonValue.boolHighlightUi:
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
                raise ValueError(
                    f"Could not find right 'category'(uia/html/image) value in the selector: {selector}"
                )


@overload
def get_element_with_pre_delay(
    selector: SelectorWindow | SelectorUia,
    preDelay: int = 300,
) -> tuple[uiautomation.Control, DictUiaAttr]: ...


@overload
def get_element_with_pre_delay(
    selector: SelectorHtml,
    preDelay: int = 300,
) -> tuple[None, DictHtmlAttr]: ...


@overload
def get_element_with_pre_delay(
    selector: SelectorImage,
    preDelay: int = 300,
) -> tuple[None, DictImageAttr]: ...


def get_element_with_pre_delay(
    selector: Selector,
    preDelay: int = 300,
) -> (
    tuple[uiautomation.Control, DictUiaAttr]
    | tuple[None, DictHtmlAttr]
    | tuple[None, DictImageAttr]
):
    """Calculate the time-consuming of get element, if it's more than preDelay, didn't need to delay."""

    timeStart = monotonic()
    temp = get_element(selector=selector)
    # log.debug(temp)
    timeUsed = (monotonic() - timeStart) * 1000
    if timeUsed < preDelay:
        delay(preDelay - int(timeUsed))

    return temp


def activate_element_window(selector: Selector) -> None:

    validate_selector(selector=selector)

    with uiautomation.UIAutomationInitializerInThread():
        # Find and activate top control.
        controlTop = get_top_control(selectorWindowPart=selector["window"])
        activate_control_window(control=controlTop)


if __name__ == "__main__":
    ...
