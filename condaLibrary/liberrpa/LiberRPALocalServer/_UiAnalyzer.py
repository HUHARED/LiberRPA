# FileName: _UiAnalyzer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Basic import delay
import liberrpa.UI._UiElement as _UiElement
from liberrpa.UI._UiAutomation import get_control_secondary_attr, get_top_control
from liberrpa.UiInterface import highlight
from liberrpa.UI._Overlay import create_overlay
from liberrpa.UI._ScreenshotPath import (
    PATH_SCREENSHOT_DOCUMENTS,
    STR_SCREENSHOT_TEMP_NAME,
)
from liberrpa.UI._Screenshot import create_screenshot_manually
from liberrpa.UI._Image import find_image
from liberrpa.Mouse import get_mouse_position
from liberrpa.Dialog import show_notification
from liberrpa.UI._UiDict import (
    DictUiAnalyzerIndicateResult,
    DictHtmlAttr,
    DictSpecImage,
    DictHtmlSecondaryAttr,
    DictImageAttr,
    SelectorWindow,
    SelectorHtml,
    SelectorImage,
    Selector,
    DictPosition,
)
from liberrpa.UI._SelectorValidation import (
    ensure_selector_window,
    ensure_selector_uia,
    ensure_selector_html,
    ensure_selector_image,
    validate_selector,
)
from liberrpa.Common._Exception import (
    ChromeElementNotFoundError,
    UiElementNotFoundError,
    UiOperationError,
    UiTimeoutError,
)
from liberrpa.Common._Chrome import (
    get_element_attr_by_coordinates,
    get_element_selector_by_coordinates,
)
import liberrpa.LiberRPALocalServer._Hook as _Hook
import liberrpa.LiberRPALocalServer._Qt as _Qt

import uiautomation
import threading
import time
from datetime import datetime
from pathvalidate import sanitize_filename as _sanitize_filename
import mss
import io
import base64
from PIL import Image
from typing import Literal


_HIGHLIGHT_DURATION = 500

# This timeout is only for user interaction after the indicate delay.
# It is unrelated to selector search timeouts or Chrome business timeouts.
_INDICATE_TIMEOUT_SECONDS = (
    15  # create_screenshot_manually in _Screenshot.py use an argument to manage.
)
_INDICATE_REFRESH_INTERVAL_SECONDS = 0.5

# Keep the generated Windows filename component within the common 255-character limit.
_INT_IMAGE_FILE_NAME_MAX_LENGTH = 255

# The fallback only examines the native desktop host under the cursor, never all applications.
_INT_DESKTOP_HIT_TEST_MAX_DEPTH = 16
_INT_DESKTOP_HIT_TEST_MAX_CONTROLS = 1024
_SET_DESKTOP_HOST_CLASS_NAME = frozenset({"Progman", "WorkerW"})
_SET_DESKTOP_CONTROL_CLASS_NAME = frozenset({
    "Progman",
    "WorkerW",
    "SHELLDLL_DefView",
    "SysListView32",
})


type Tuple_IndicateOverlayState = tuple[int, int, int, int, str]


class UiAnalyzerOperationCanceledError(RuntimeError):
    """Raised when the UI Analyzer client owning an operation disconnects."""


def _raise_if_operation_canceled(
    eventCancelRequested: threading.Event | None,
) -> None:
    if eventCancelRequested is not None and eventCancelRequested.is_set():
        raise UiAnalyzerOperationCanceledError(
            "The UI Analyzer operation was canceled because its client disconnected."
        )


def _is_validation_no_match_error(e: Exception) -> bool:
    """Return whether validation completed normally but no target matched before the timeout."""
    if isinstance(e, (UiElementNotFoundError, ChromeElementNotFoundError)):
        return True

    return type(e) is UiTimeoutError and isinstance(
        e.__cause__,
        (UiElementNotFoundError, ChromeElementNotFoundError),
    )


def _update_indicate_overlay(
    previousState: Tuple_IndicateOverlayState | None,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str = "",
) -> Tuple_IndicateOverlayState:
    currentState: Tuple_IndicateOverlayState = (
        x,
        y,
        width,
        height,
        label,
    )

    if currentState != previousState:
        _Qt.update_indicate_overlay(
            x=x,
            y=y,
            width=width,
            height=height,
            color="red",
            label=label,
        )

    return currentState


def _close_indicate_overlay() -> None:
    try:
        _Qt.close_indicate_overlay()
    except Exception as e:
        Log.exception_info(e)


def _wait_for_next_indicate_refresh(
    deadline: float,
    eventCancelRequested: threading.Event | None,
) -> None:
    _raise_if_operation_canceled(eventCancelRequested)
    floatRemainingSeconds = deadline - time.monotonic()
    if floatRemainingSeconds <= 0:
        return

    floatWaitSeconds = min(
        _INDICATE_REFRESH_INTERVAL_SECONDS,
        floatRemainingSeconds,
    )
    if eventCancelRequested is None:
        time.sleep(floatWaitSeconds)
    elif eventCancelRequested.wait(timeout=floatWaitSeconds):
        _raise_if_operation_canceled(eventCancelRequested)


@Log.trace()
def indicate_uia(
    indicateDelaySeconds: int = 1,
    *,
    eventCancelRequested: threading.Event | None = None,
) -> DictUiAnalyzerIndicateResult | None:
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(
                indicateDelaySeconds,
                eventCancelRequested=eventCancelRequested,
            )
            deadline = _create_deadline()
            threadHook = _start_hook(eventCancelRequested=eventCancelRequested)
            dictCoordinate: DictPosition | None = None
            element: uiautomation.Control | None = None
            tupleOverlayState: Tuple_IndicateOverlayState | None = None
            tupleElementRectangle: tuple[int, int, int, int] | None = None
            strControlTypeName: str | None = None

            # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
            while _Hook.should_continue_hook():
                if _has_timed_out(deadline):
                    _raise_indicate_timeout("indicate_uia")

                try:
                    dictCoordinate = get_mouse_position()
                    Log.debug("Position: " + str(dictCoordinate))
                    element = _get_indicate_control_from_point(dictCoordinate)

                    # Avoid logging the Control object because __str__() queries multiple COM properties.
                    # Log.debug("Get element: " + str(element))

                    if element is not None:
                        rectangle = element.BoundingRectangle
                        strControlTypeName = element.ControlTypeName

                        tupleElementRectangle = (
                            rectangle.left,
                            rectangle.top,
                            rectangle.width(),
                            rectangle.height(),
                        )

                        Log.debug({
                            "controlType": strControlTypeName,
                            "rectangle": tupleElementRectangle,
                        })
                    else:
                        Log.debug("element is None.")
                except Exception as e:
                    strError = (
                        f"Error to get UI element at {dictCoordinate}. If the error persists, you may need to restart LiberRPA Local Server, then try to find another element in the window, then locate the target element by Element Tree, or try to indicate an image instead of uia element.\n"
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(
                        title="UI Analyzer Error",
                        message=strError,
                        duration=5,
                        wait=False,
                    )
                    raise

                if (
                    element is None
                    or tupleElementRectangle is None
                    or strControlTypeName is None
                ):
                    raise UiElementNotFoundError(
                        "No UI element was captured before the indication stopped."
                    )

                tupleOverlayState = _update_indicate_overlay(
                    tupleOverlayState,
                    x=tupleElementRectangle[0],
                    y=tupleElementRectangle[1],
                    width=tupleElementRectangle[2],
                    height=tupleElementRectangle[3],
                    label=strControlTypeName,
                )
                _wait_for_next_indicate_refresh(
                    deadline,
                    eventCancelRequested,
                )

            _raise_if_operation_canceled(eventCancelRequested)

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_uia",
                eventCancelRequested=eventCancelRequested,
            )

            # Resolve the element again at the exact mouse-down position after the complete click has been suppressed.
            # The preview result may otherwise be up to one refresh interval old.
            _close_indicate_overlay()
            element, tupleElementRectangle, strControlTypeName = (
                _get_uia_element_at_position(dictCoordinate=dictCoordinate)
            )
            _raise_if_operation_canceled(eventCancelRequested)
            Log.debug({
                "message": "Pressed mouse left.",
                "position": dictCoordinate,
                "controlType": strControlTypeName,
                "rectangle": tupleElementRectangle,
                "targetIdentity": _get_hit_test_identity(element),
            })

            # Get the selector(contains primary attributes) and secondary attributes.
            selectorBuilt, listRecommendedSpecification = (
                _UiElement.get_control_selector_with_recommendation(
                    control=element,
                    targetRectangle=tupleElementRectangle,
                )
            )
            selector = ensure_selector_uia(selectorBuilt)
            if listRecommendedSpecification is None:
                raise UiOperationError(
                    "A UIA indication did not produce a UIA selector recommendation."
                )

            controlWindow = _UiElement.get_control_window(control=element)
            dictRecommendedWindow = _UiElement.get_recommended_window_selector_part(
                control=controlWindow,
                dictAllWindowAttributes=selector["window"],
            )
            dictSecondaryAttr = get_control_secondary_attr(
                control=element,
                rectangle=tupleElementRectangle,
            )
            _raise_if_operation_canceled(eventCancelRequested)

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )
        _raise_if_operation_canceled(eventCancelRequested)

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
            "preview": preview,
            "recommendedWindow": dictRecommendedWindow,
            "recommendedSpecification": listRecommendedSpecification,
        }
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({
            "selector": selector,
            "recommendedWindow": dictRecommendedWindow,
            "recommendedSpecification": listRecommendedSpecification,
            "attributes": dictSecondaryAttr,
        })
        return dictReturn

    finally:
        _close_indicate_overlay()
        _stop_hook_thread(
            threadHook,
            source="indicate_uia",
        )


@Log.trace()
def indicate_chrome(
    indicateDelaySeconds: int = 1,
    usePath: bool = True,
    *,
    eventCancelRequested: threading.Event | None = None,
) -> tuple[DictUiAnalyzerIndicateResult, DictPosition] | None:
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(
                indicateDelaySeconds,
                eventCancelRequested=eventCancelRequested,
            )
            deadline = _create_deadline()
            threadHook = _start_hook(eventCancelRequested=eventCancelRequested)
            dictCoordinate: DictPosition | None = None
            dictSecondaryAttr: DictHtmlSecondaryAttr | None = None
            tupleOverlayState: Tuple_IndicateOverlayState | None = None

            # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
            listAllAttr: list[DictHtmlAttr] = []
            while _Hook.should_continue_hook():
                if _has_timed_out(deadline):
                    _raise_indicate_timeout("indicate_chrome")

                try:
                    dictCoordinate = get_mouse_position()
                    # Call Chrome
                    # listAllAttr: list[DictHtmlAttr],
                    listAllAttr = get_element_attr_by_coordinates(
                        x=dictCoordinate["x"], y=dictCoordinate["y"], usePath=usePath
                    )
                    dictSecondaryAttr = {
                        "secondary-x": listAllAttr[-1]["secondary-x"],
                        "secondary-y": listAllAttr[-1]["secondary-y"],
                        "secondary-width": listAllAttr[-1]["secondary-width"],
                        "secondary-height": listAllAttr[-1]["secondary-height"],
                    }

                    # Highlight the last element in the list.
                    strLabel = (
                        f"<{listAllAttr[-1].get('tagName', '')}> "
                        f"{listAllAttr[-1].get('id', '')} "
                        f"{listAllAttr[-1].get('name', '')}"
                    ).strip()
                    tupleOverlayState = _update_indicate_overlay(
                        tupleOverlayState,
                        x=int(dictSecondaryAttr["secondary-x"]),
                        y=int(dictSecondaryAttr["secondary-y"]),
                        width=int(dictSecondaryAttr["secondary-width"]),
                        height=int(dictSecondaryAttr["secondary-height"]),
                        label=strLabel,
                    )
                    _wait_for_next_indicate_refresh(
                        deadline,
                        eventCancelRequested,
                    )

                except UiAnalyzerOperationCanceledError:
                    raise
                except Exception as e:
                    strError = (
                        f"Error to get UI element at {dictCoordinate}. If the error persists, you may need to restart LiberRPA Local Server, restart Chrome, or try to indicate an image.\n"
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(
                        title="UI Analyzer Error",
                        message=strError,
                        duration=5,
                        wait=False,
                    )
                    raise

            _raise_if_operation_canceled(eventCancelRequested)

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_chrome",
                eventCancelRequested=eventCancelRequested,
            )

            # Resolve the Chrome element again at the exact mouse-down position after the complete click has been suppressed.
            # Recommendation analysis runs only for this final target, never during hover refreshes.
            _close_indicate_overlay()
            dictSelectorRecommendation = get_element_selector_by_coordinates(
                x=dictCoordinate["x"],
                y=dictCoordinate["y"],
                usePath=usePath,
            )
            _raise_if_operation_canceled(eventCancelRequested)
            listAllAttr = dictSelectorRecommendation["allLayerAttributes"]
            listRecommendedSpecification = dictSelectorRecommendation[
                "recommendedSpecification"
            ]
            if len(listAllAttr) == 0:
                raise UiElementNotFoundError(
                    f"No Chrome element was found at {dictCoordinate}."
                )

            dictSecondaryAttr = {
                "secondary-x": listAllAttr[-1]["secondary-x"],
                "secondary-y": listAllAttr[-1]["secondary-y"],
                "secondary-width": listAllAttr[-1]["secondary-width"],
                "secondary-height": listAllAttr[-1]["secondary-height"],
            }
            Log.debug({
                "message": "Pressed mouse left.",
                "position": dictCoordinate,
                "rectangle": (
                    dictSecondaryAttr["secondary-x"],
                    dictSecondaryAttr["secondary-y"],
                    dictSecondaryAttr["secondary-width"],
                    dictSecondaryAttr["secondary-height"],
                ),
            })

            # Delete all secondary attributes in listAllAttr, assign it to listSpecification
            listSpecification: list[dict[str, object]] = []
            for dictAttr in listAllAttr:
                dictToAppendTemp: dict[str, object] = {}

                for strKey in dictAttr:
                    if not strKey.startswith("secondary-"):
                        dictToAppendTemp[strKey] = dictAttr[strKey]

                listSpecification.append(dictToAppendTemp)

            # After click, get the window element once.
            elementWindow = _get_window_element(dictCoordinate=dictCoordinate)

            dictWindowSelector = ensure_selector_window(
                _UiElement.get_control_selector(control=elementWindow)
            )["window"]
            dictRecommendedWindow = _UiElement.get_recommended_window_selector_part(
                control=elementWindow,
                dictAllWindowAttributes=dictWindowSelector,
            )
            selector: SelectorHtml = ensure_selector_html({
                "window": dictWindowSelector,
                "category": "html",
                "specification": listSpecification,
            })
            selectorRecommended: SelectorHtml = ensure_selector_html({
                "window": dictWindowSelector,
                "category": "html",
                "specification": listRecommendedSpecification,
            })
            _raise_if_operation_canceled(eventCancelRequested)

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )
        _raise_if_operation_canceled(eventCancelRequested)

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
            "preview": preview,
            "recommendedWindow": dictRecommendedWindow,
            "recommendedSpecification": selectorRecommended["specification"],
        }
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({
            "selector": selector,
            "recommendedWindow": dictRecommendedWindow,
            "recommendedSpecification": selectorRecommended["specification"],
            "attributes": dictSecondaryAttr,
        })
        return (dictReturn, dictCoordinate)

    finally:
        _close_indicate_overlay()
        _stop_hook_thread(
            threadHook,
            source="indicate_chrome",
        )


def _create_image_file_name(windowName: str) -> str:
    strSuffix = "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
    intPrefixLimit = _INT_IMAGE_FILE_NAME_MAX_LENGTH - len(strSuffix)

    strTitle = (windowName or "window").replace(" - Google Chrome", "")
    # Preserve the existing ASCII-only filename policy used for image matching.
    strAsciiTitle = "".join(char for char in strTitle if char.isascii())
    strPrefix = _sanitize_filename(
        filename=strAsciiTitle,
        platform="Windows",
        max_len=intPrefixLimit,
        fs_encoding="ascii",
    )
    # Reserved-name replacement may add characters after the sanitizer's truncation.
    strPrefix = strPrefix[:intPrefixLimit].strip(" .") or "window"
    return strPrefix + strSuffix


@Log.trace()
def indicate_image(
    indicateDelaySeconds: int = 1,
    grayscale: bool = True,
    confidence: float = 0.9,
    *,
    eventCancelRequested: threading.Event | None = None,
) -> DictUiAnalyzerIndicateResult | None:

    with uiautomation.UIAutomationInitializerInThread():
        _delay(
            indicateDelaySeconds,
            eventCancelRequested=eventCancelRequested,
        )

        if not create_screenshot_manually(
            timeoutSeconds=15,
            eventCancelRequested=eventCancelRequested,
        ):
            _raise_if_operation_canceled(eventCancelRequested)
            Log.debug("Quit indicating.")
            return None

        _raise_if_operation_canceled(eventCancelRequested)

        # After Screenshot, get window selector to generate image selector.
        dictCoordinate = get_mouse_position()
        # time.sleep(0.1)
        elementWindow = _get_window_element(dictCoordinate=dictCoordinate)
        Log.verbose("Retrieved the top-level window for the image selector.")

        strNewFileName = _create_image_file_name(windowName=elementWindow.Name)
        Log.debug(strNewFileName)
        _raise_if_operation_canceled(eventCancelRequested)
        # Both files are in the same folder. On Windows, rename refuses to replace an existing file and never treats an existing destination directory as a container.
        (PATH_SCREENSHOT_DOCUMENTS / STR_SCREENSHOT_TEMP_NAME).rename(
            PATH_SCREENSHOT_DOCUMENTS / strNewFileName
        )

        strGrayscale: Literal["true", "false"] = "true" if grayscale else "false"
        dictWindowSelector = ensure_selector_window(
            _UiElement.get_control_selector(control=elementWindow)
        )["window"]
        dictRecommendedWindow = _UiElement.get_recommended_window_selector_part(
            control=elementWindow,
            dictAllWindowAttributes=dictWindowSelector,
        )
        selector: SelectorImage = ensure_selector_image({
            "window": dictWindowSelector,
            "category": "image",
            "specification": [
                {
                    "FileName": strNewFileName,
                    "Grayscale": strGrayscale,
                    "Confidence": str(confidence),
                }
            ],
        })

    _raise_if_operation_canceled(eventCancelRequested)
    listDictImageAttr = find_image(
        fileNameOrPath=strNewFileName,
        region=None,
        confidence=confidence,
        grayscale=grayscale,
        limit=1,
        moveFile=False,
        inScreenshotFolder=True,
    )
    if len(listDictImageAttr) == 0:
        raise UiElementNotFoundError(
            f"Can't validate the image '{strNewFileName}' after your selection, grayscale={grayscale}, confidence={confidence}"
        )
    dictSecondaryAttr: DictImageAttr = listDictImageAttr[0]
    _raise_if_operation_canceled(eventCancelRequested)

    preview = _screenshot_to_base64(
        x=int(dictSecondaryAttr["secondary-x"]),
        y=int(dictSecondaryAttr["secondary-y"]),
        width=int(dictSecondaryAttr["secondary-width"]),
        height=int(dictSecondaryAttr["secondary-height"]),
    )

    _raise_if_operation_canceled(eventCancelRequested)
    create_overlay(
        x=int(dictSecondaryAttr["secondary-x"]),
        y=int(dictSecondaryAttr["secondary-y"]),
        width=int(dictSecondaryAttr["secondary-width"]),
        height=int(dictSecondaryAttr["secondary-height"]),
        duration=_HIGHLIGHT_DURATION,
    )

    dictReturn: DictUiAnalyzerIndicateResult = {
        "selector": selector,
        "attributes": dictSecondaryAttr,
        "preview": preview,
        "recommendedWindow": dictRecommendedWindow,
    }
    # Log.debug(dictReturn)
    # preview is so long, not print it.
    Log.debug({
        "selector": selector,
        "recommendedWindow": dictRecommendedWindow,
        "attributes": dictSecondaryAttr,
    })
    return dictReturn


@Log.trace()
def indicate_window(
    indicateDelaySeconds: int = 1,
    *,
    eventCancelRequested: threading.Event | None = None,
) -> DictUiAnalyzerIndicateResult | None:
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(
                indicateDelaySeconds,
                eventCancelRequested=eventCancelRequested,
            )
            deadline = _create_deadline()
            threadHook = _start_hook(eventCancelRequested=eventCancelRequested)
            dictCoordinate: DictPosition | None = None
            element: uiautomation.Control | None = None
            tupleOverlayState: Tuple_IndicateOverlayState | None = None
            tupleElementRectangle: tuple[int, int, int, int] | None = None

            # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
            while _Hook.should_continue_hook():
                if _has_timed_out(deadline):
                    _raise_indicate_timeout("indicate_window")

                try:
                    dictCoordinate = get_mouse_position()
                    # Find the element under the cursor
                    # print("Get element.")

                    control = _get_indicate_control_from_point(dictCoordinate)

                    if control is None:
                        raise UiElementNotFoundError(
                            "Failed to get top-level control from point."
                        )

                    # Store the current lookup in candidate variables first.
                    # Commit them only after both the element and its rectangle are retrieved successfully, so a failed refresh cannot corrupt the last valid result.
                    elementCandidate = _UiElement.get_control_window(control=control)

                    rectangle = elementCandidate.BoundingRectangle
                    tupleCandidateRectangle = (
                        rectangle.left,
                        rectangle.top,
                        rectangle.width(),
                        rectangle.height(),
                    )

                except Exception as e:
                    strError = (
                        f"Error to get window at {dictCoordinate}. "
                        "LiberRPA Local Server may not have permission to access the window. "
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(
                        title="UI Analyzer Error",
                        message=strError,
                        duration=2,
                        wait=False,
                    )
                    _wait_for_next_indicate_refresh(
                        deadline,
                        eventCancelRequested,
                    )
                    continue

                element = elementCandidate
                tupleElementRectangle = tupleCandidateRectangle

                tupleOverlayState = _update_indicate_overlay(
                    tupleOverlayState,
                    x=tupleElementRectangle[0],
                    y=tupleElementRectangle[1],
                    width=tupleElementRectangle[2],
                    height=tupleElementRectangle[3],
                )
                _wait_for_next_indicate_refresh(
                    deadline,
                    eventCancelRequested,
                )

            _raise_if_operation_canceled(eventCancelRequested)

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_window",
                eventCancelRequested=eventCancelRequested,
            )

            # Resolve the window again at the exact mouse-down position after the complete click has been suppressed.
            _close_indicate_overlay()
            element, tupleElementRectangle = _get_window_element_at_position(
                dictCoordinate=dictCoordinate
            )
            _raise_if_operation_canceled(eventCancelRequested)
            Log.debug({
                "message": "Pressed mouse left.",
                "position": dictCoordinate,
                "rectangle": tupleElementRectangle,
            })

            selector: SelectorWindow = ensure_selector_window(
                _UiElement.get_control_selector(
                    control=element,
                    targetRectangle=tupleElementRectangle,
                )
            )
            dictRecommendedWindow = _UiElement.get_recommended_window_selector_part(
                control=element,
                dictAllWindowAttributes=selector["window"],
                targetRectangle=tupleElementRectangle,
            )
            dictSecondaryAttr = get_control_secondary_attr(
                control=element,
                rectangle=tupleElementRectangle,
            )
            _raise_if_operation_canceled(eventCancelRequested)

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
            "recommendedWindow": dictRecommendedWindow,
        }
        Log.debug(dictReturn)
        return dictReturn

    finally:
        _close_indicate_overlay()
        _stop_hook_thread(
            threadHook,
            source="indicate_window",
        )


@Log.trace()
def validate(
    selector: Selector,
    timeout: int,
    *,
    eventCancelRequested: threading.Event | None = None,
) -> dict[str, bool]:
    try:
        _raise_if_operation_canceled(eventCancelRequested)
        validate_selector(selector=selector)
        _raise_if_operation_canceled(eventCancelRequested)

        if selector.get("category") != "image":
            highlight(
                selector=selector,
                color="red",
                duration=2000,
                timeout=timeout * 1000,
                preDelay=0,
                postDelay=0,
            )
            _raise_if_operation_canceled(eventCancelRequested)
        else:
            """If use highlight() directly, image file will be moved to LiberRPALocalServer/screenshot. So create a function similar with _UiElement.get_element but not move file."""
            from liberrpa.UI._TerminableThread import timeout_kill_thread

            timeout = _UiElement.check_set_timeout(timeout=timeout * 1000)

            selectorTemp: SelectorImage = ensure_selector_image(selector)

            _, dictTarget = timeout_kill_thread(timeout=timeout)(_get_image_element)(
                selectorTemp
            )
            _raise_if_operation_canceled(eventCancelRequested)
            create_overlay(
                x=int(dictTarget["secondary-x"]),
                y=int(dictTarget["secondary-y"]),
                width=int(dictTarget["secondary-width"]),
                height=int(dictTarget["secondary-height"]),
                color="red",
                duration=2000,
            )
            _raise_if_operation_canceled(eventCancelRequested)

    except UiAnalyzerOperationCanceledError:
        raise
    except Exception as e:
        if _is_validation_no_match_error(e):
            Log.debug(f"Selector validation did not find a matching target: {e}")
            return {"validate": False}

        Log.exception_info(e)
        raise
    else:
        # Highlight success.
        return {"validate": True}


def _get_mouse_selection_position(
    *,
    deadline: float,
    indicateName: str,
    eventCancelRequested: threading.Event | None,
) -> DictPosition:
    _raise_if_operation_canceled(eventCancelRequested)
    tupleMousePosition = _Hook.get_mouse_left_position()
    if tupleMousePosition is None:
        raise UiElementNotFoundError("The mouse selection position was not captured.")

    while True:
        _raise_if_operation_canceled(eventCancelRequested)
        floatRemainingSeconds = deadline - time.monotonic()
        if floatRemainingSeconds <= 0:
            _raise_indicate_timeout(f"{indicateName} mouse release")

        if _Hook.wait_mouse_left_released(
            timeout=min(_INDICATE_REFRESH_INTERVAL_SECONDS, floatRemainingSeconds)
        ):
            break

    _raise_if_operation_canceled(eventCancelRequested)
    return {
        "x": tupleMousePosition[0],
        "y": tupleMousePosition[1],
    }


def _get_hit_test_identity(control: uiautomation.Control | None) -> dict[str, object]:
    """Read a few diagnostic properties without calling Control.__str__()."""
    if control is None:
        return {"missing": True}

    dictIdentity: dict[str, object] = {}
    for strPropertyName in (
        "ControlTypeName",
        "ClassName",
        "Name",
        "ProcessId",
        "NativeWindowHandle",
    ):
        try:
            value = getattr(control, strPropertyName)
            dictIdentity[strPropertyName] = (
                value[:160] if isinstance(value, str) else value
            )
        except Exception as e:
            dictIdentity[strPropertyName] = f"<unavailable: {type(e).__name__}>"
    return dictIdentity


def _is_desktop_host_control(
    control: uiautomation.Control,
    controlRoot: uiautomation.Control,
) -> bool:
    if control.ClassName not in _SET_DESKTOP_CONTROL_CLASS_NAME:
        return False

    controlCurrent: uiautomation.Control | None = control
    for _intDepth in range(_INT_DESKTOP_HIT_TEST_MAX_DEPTH):
        if controlCurrent is None or uiautomation.ControlsAreSame(
            controlCurrent, controlRoot
        ):
            return False
        if controlCurrent.ClassName in _SET_DESKTOP_HOST_CLASS_NAME:
            return True
        controlCurrent = controlCurrent.GetParentControl()
    return False


def _get_desktop_descendant_at_position(
    controlHost: uiautomation.Control,
    dictCoordinate: DictPosition,
) -> uiautomation.Control:
    """Refine a native desktop host to a unique visible descendant under the cursor."""
    intX, intY = dictCoordinate["x"], dictCoordinate["y"]
    controlCurrent = controlHost
    intVisitedControlCount = 0

    for _intDepth in range(_INT_DESKTOP_HIT_TEST_MAX_DEPTH):
        listMatchingChild: list[uiautomation.Control] = []
        for controlChild in controlCurrent.GetChildren():
            intVisitedControlCount += 1
            if intVisitedControlCount > _INT_DESKTOP_HIT_TEST_MAX_CONTROLS:
                raise UiElementNotFoundError(
                    "Desktop UIA hit testing exceeded its control limit."
                )

            try:
                rectangle = controlChild.BoundingRectangle
                boolContainsPoint = (
                    rectangle.left <= intX < rectangle.right
                    and rectangle.top <= intY < rectangle.bottom
                )
                if boolContainsPoint and not controlChild.IsOffscreen:
                    listMatchingChild.append(controlChild)
            except Exception:
                # A shell item may disappear between enumeration and property retrieval.
                continue

        if not listMatchingChild:
            return controlCurrent
        if len(listMatchingChild) != 1:
            raise UiElementNotFoundError(
                "Desktop UIA hit testing found overlapping child controls; "
                "refusing to choose an arbitrary target."
            )
        controlCurrent = listMatchingChild[0]

    raise UiElementNotFoundError("Desktop UIA hit testing exceeded its depth limit.")


def _get_indicate_control_from_point(
    dictCoordinate: DictPosition,
) -> uiautomation.Control | None:
    control = uiautomation.ControlFromPoint(x=dictCoordinate["x"], y=dictCoordinate["y"])
    if control is None:
        return None

    controlRoot = uiautomation.GetRootControl()
    if not uiautomation.ControlsAreSame(control, controlRoot):
        return control

    # UIA's point provider returned the desktop root, not the item under the pointer.
    # Try the native HWND route, but only refine a verified desktop shell subtree.
    controlNative = uiautomation.ControlFromPoint2(
        x=dictCoordinate["x"],
        y=dictCoordinate["y"],
    )
    dictDiagnostic = {
        "message": "UIA point hit returned the desktop root.",
        "position": dictCoordinate,
        "uiaHit": _get_hit_test_identity(control),
        "nativeHit": _get_hit_test_identity(controlNative),
    }
    Log.debug(dictDiagnostic)

    if controlNative is None or not _is_desktop_host_control(controlNative, controlRoot):
        raise UiElementNotFoundError(
            "UIA hit testing returned the desktop root instead of a selectable element, "
            "and the native hit did not identify a desktop shell host. "
            f"nativeHit={dictDiagnostic['nativeHit']!r}."
        )

    controlRecovered = _get_desktop_descendant_at_position(controlNative, dictCoordinate)
    Log.debug({
        "message": "Resolved the desktop UIA target through its native host.",
        "position": dictCoordinate,
        "target": _get_hit_test_identity(controlRecovered),
    })
    return controlRecovered


def _get_uia_element_at_position(
    *,
    dictCoordinate: DictPosition,
    retryCount: int = 3,
) -> tuple[uiautomation.Control, tuple[int, int, int, int], str]:
    exceptionLast: Exception | None = None

    for intAttempt in range(retryCount):
        try:
            control = _get_indicate_control_from_point(dictCoordinate)
            if control is None:
                raise UiElementNotFoundError(
                    f"No UI element was found at {dictCoordinate}."
                )

            rectangle = control.BoundingRectangle
            tupleRectangle = (
                rectangle.left,
                rectangle.top,
                rectangle.width(),
                rectangle.height(),
            )
            return control, tupleRectangle, control.ControlTypeName

        except Exception as e:
            exceptionLast = e
            if intAttempt + 1 < retryCount:
                time.sleep(0.03)

    raise UiElementNotFoundError(
        f"Failed to resolve the selected UI element at {dictCoordinate}."
    ) from exceptionLast


def _get_window_element_at_position(
    *,
    dictCoordinate: DictPosition,
) -> tuple[uiautomation.Control, tuple[int, int, int, int]]:
    control = _get_indicate_control_from_point(dictCoordinate)
    if control is None:
        raise UiElementNotFoundError(f"No UI element was found at {dictCoordinate}.")

    elementWindow = _UiElement.get_control_window(control=control)
    rectangle = elementWindow.BoundingRectangle
    return elementWindow, (
        rectangle.left,
        rectangle.top,
        rectangle.width(),
        rectangle.height(),
    )


def _create_deadline() -> float:
    return time.monotonic() + _INDICATE_TIMEOUT_SECONDS


def _has_timed_out(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _raise_indicate_timeout(indicateName: str) -> None:
    raise TimeoutError(
        f"{indicateName} timed out after {_INDICATE_TIMEOUT_SECONDS} seconds."
    )


def _delay(
    indicateDelaySeconds: int,
    *,
    eventCancelRequested: threading.Event | None,
) -> None:
    _raise_if_operation_canceled(eventCancelRequested)
    if indicateDelaySeconds <= 0:
        return

    if eventCancelRequested is None:
        delay(indicateDelaySeconds * 1000)
        return

    if eventCancelRequested.wait(timeout=indicateDelaySeconds):
        _raise_if_operation_canceled(eventCancelRequested)


def _start_hook(
    *,
    eventCancelRequested: threading.Event | None,
) -> threading.Thread:
    _raise_if_operation_canceled(eventCancelRequested)
    threadHook = _Hook.start_hook()

    if eventCancelRequested is not None and eventCancelRequested.is_set():
        _Hook.stop_hook(
            threadHook,
            source="operation_canceled_during_hook_start",
            timeoutSeconds=2,
        )
        _raise_if_operation_canceled(eventCancelRequested)

    return threadHook


def _stop_hook_thread(
    threadHook: threading.Thread | None,
    source: str,
) -> None:
    Log.debug("Clean up hook thread.")

    if threadHook is None:
        return

    _Hook.stop_hook(
        threadHook,
        source=source,
        timeoutSeconds=2,
    )


def _get_window_element(dictCoordinate: DictPosition) -> uiautomation.Control:
    """Get and highlight the window of Chrome and Image element."""

    elementWindow, tupleRectangle = _get_window_element_at_position(
        dictCoordinate=dictCoordinate
    )
    create_overlay(
        x=tupleRectangle[0],
        y=tupleRectangle[1],
        width=tupleRectangle[2],
        height=tupleRectangle[3],
        color="red",
        duration=_HIGHLIGHT_DURATION,
    )

    return elementWindow


def _screenshot_to_base64(x: int, y: int, width: int, height: int) -> str:
    with mss.mss() as sct:
        # Define the region for the screenshot
        monitor = {"top": y, "left": x, "width": width, "height": height}

        # Grab the data
        imageScreenshot = sct.grab(monitor)

        # Convert to PIL Image
        imageTemp = Image.frombytes("RGB", imageScreenshot.size, imageScreenshot.rgb)

        # Compress if height > 40 px, so it will be sent to UI Analyzer faster and suit the UI Analyzer Preview area's size.
        intMaxHeight = 40
        if height > intMaxHeight:
            scaleFactor = intMaxHeight / height  # Calculate scale factor
            intNewWidth = int(width * scaleFactor)
            imageTemp = imageTemp.resize(
                (intNewWidth, intMaxHeight), Image.Resampling.LANCZOS
            )  # Resize proportionally

        # Create an in-memory bytes buffer
        imageByte = io.BytesIO()
        imageTemp.save(imageByte, format="PNG")  # Save image to the byte stream as PNG
        imageByte.seek(0)  # Move to the beginning of the stream

        # Encode this image as base64
        strBase64 = base64.b64encode(imageByte.getvalue()).decode("utf-8")
        # print("Size of image:", strBase64.__len__())
        return strBase64


def _get_image_element(
    selector: SelectorImage,
) -> tuple[None, DictImageAttr]:
    """a reduced version of _UiElement.get_element, for get imgae element and not move the file."""

    with uiautomation.UIAutomationInitializerInThread():
        # Find and activate top control.
        controlTop = get_top_control(selectorWindowPart=selector["window"])
        _UiElement.activate_control_window(control=controlTop)

        selectorTemp: SelectorImage = selector
        if len(selectorTemp["specification"]) != 1:
            raise ValueError(
                f"It should have only one dictionary in 'specification', but it has {len(selectorTemp['specification'])}"
            )
        imageSelector: DictSpecImage = selectorTemp["specification"][0]

        rectangle = controlTop.BoundingRectangle
        listDictImageAttr = find_image(
            fileNameOrPath=imageSelector["FileName"],
            region=(
                rectangle.left,
                rectangle.top,
                rectangle.width(),
                rectangle.height(),
            ),
            confidence=float(imageSelector["Confidence"]),
            grayscale=True if imageSelector["Grayscale"] == "true" else False,
            # If have no Index or Index = "0", limit should be 1, else limit should be Index+1, due to All Index in LiberRPA selector start from 0.
            limit=int(imageSelector.get("Index", "0")) + 1,
            moveFile=False,
            inScreenshotFolder=True,
        )

    # The list's length has limited by Index, but it may not find enough image(0 or less than Index+1), so check it.
    if len(listDictImageAttr) < int(imageSelector.get("Index", "0")) + 1:
        raise UiElementNotFoundError(
            f"Not Found image element. selector's specification: {imageSelector}"
        )
    # length = Index+1, return the last one.
    return (None, listDictImageAttr[-1])


if __name__ == "__main__":
    with uiautomation.UIAutomationInitializerInThread():
        element = uiautomation.ControlFromPoint(x=400, y=140)
        print(element)
        if element:
            create_overlay(
                element.BoundingRectangle.left,
                element.BoundingRectangle.top,
                element.BoundingRectangle.width(),
                element.BoundingRectangle.height(),
                color="red",
                duration=_HIGHLIGHT_DURATION,
            )
