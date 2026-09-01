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
    DictElementTreeItem,
)
from liberrpa.UI._SelectorValidation import (
    ensure_selector_window,
    ensure_selector_uia,
    ensure_selector_html,
    ensure_selector_image,
    validate_selector,
)
from liberrpa.Common._Exception import UiElementNotFoundError
from liberrpa.Common._Chrome import get_element_attr_by_coordinates
import liberrpa.LiberRPALocalServer._Hook as _Hook
import liberrpa.LiberRPALocalServer._Qt as _Qt

import uiautomation
import threading
import time
from datetime import datetime
import shutil
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

type Tuple_IndicateOverlayState = tuple[int, int, int, int, str]


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


def _wait_for_next_indicate_refresh(deadline: float) -> None:
    floatRemainingSeconds = deadline - time.monotonic()
    if floatRemainingSeconds <= 0:
        return

    time.sleep(
        min(
            _INDICATE_REFRESH_INTERVAL_SECONDS,
            floatRemainingSeconds,
        )
    )


@Log.trace()
def indicate_uia(
    indicateDelaySeconds: int = 1,
) -> DictUiAnalyzerIndicateResult | None:
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(indicateDelaySeconds)
            deadline = _create_deadline()
            threadHook = _start_hook()
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
                    element = uiautomation.ControlFromPoint(
                        x=dictCoordinate["x"], y=dictCoordinate["y"]
                    )

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
                _wait_for_next_indicate_refresh(deadline)

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_uia",
            )

            # Resolve the element again at the exact mouse-down position after the complete click has been suppressed.
            # The preview result may otherwise be up to one refresh interval old.
            _close_indicate_overlay()
            element, tupleElementRectangle, strControlTypeName = (
                _get_uia_element_at_position(dictCoordinate=dictCoordinate)
            )
            Log.debug({
                "message": "Pressed mouse left.",
                "position": dictCoordinate,
                "controlType": strControlTypeName,
                "rectangle": tupleElementRectangle,
            })

            # Get the selector(contains primary attributes) and secondary attributes.
            selector = ensure_selector_uia(
                _UiElement.get_control_selector(
                    control=element, targetRectangle=tupleElementRectangle
                )
            )
            dictSecondaryAttr = get_control_secondary_attr(
                control=element,
                rectangle=tupleElementRectangle,
            )

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
            "preview": preview,
        }
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
        return dictReturn

    finally:
        _close_indicate_overlay()
        _stop_hook_thread(
            threadHook,
            source="indicate_uia",
        )


@Log.trace()
def indicate_chrome(
    indicateDelaySeconds: int = 1, usePath: bool = True
) -> (
    tuple[DictUiAnalyzerIndicateResult, tuple[list[DictElementTreeItem], list[int], int]]
    | None
):
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(indicateDelaySeconds)
            deadline = _create_deadline()
            threadHook = _start_hook()
            dictCoordinate: DictPosition | None = None
            dictSecondaryAttr: DictHtmlSecondaryAttr | None = None
            tupleEleTree: tuple[list[DictElementTreeItem], list[int], int] | None = None
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
                    listAllAttr, tupleEleTree = get_element_attr_by_coordinates(
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
                    _wait_for_next_indicate_refresh(deadline)

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

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_chrome",
            )

            # Resolve the Chrome element again at the exact mouse-down position after the complete click has been suppressed.
            _close_indicate_overlay()
            listAllAttr, tupleEleTree = get_element_attr_by_coordinates(
                x=dictCoordinate["x"],
                y=dictCoordinate["y"],
                usePath=usePath,
            )
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

            selector: SelectorHtml = ensure_selector_html({
                "window": ensure_selector_window(
                    _UiElement.get_control_selector(control=elementWindow)
                )["window"],
                "category": "html",
                "specification": listSpecification,
            })

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
            "preview": preview,
        }
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
        return (dictReturn, tupleEleTree)

    finally:
        _close_indicate_overlay()
        _stop_hook_thread(
            threadHook,
            source="indicate_chrome",
        )


@Log.trace()
def indicate_image(
    indicateDelaySeconds: int = 1, grayscale: bool = True, confidence: float = 0.9
) -> DictUiAnalyzerIndicateResult | None:

    with uiautomation.UIAutomationInitializerInThread():
        _delay(indicateDelaySeconds)

        if not create_screenshot_manually(timeoutSeconds=15):
            Log.debug("Quit indicating.")
            return None

        # After Screenshot, get window selector to generate  image selector
        dictCoordinate = get_mouse_position()
        # time.sleep(0.1)
        elementWindow = _get_window_element(dictCoordinate=dictCoordinate)
        Log.verbose("Retrieved the top-level window for the image selector.")

        # Rename the screenshot: window's name + datetime + .png
        # Remove some common part in it to make the name concise.
        strTemp = (elementWindow.Name or "window").replace(" - Google Chrome", "")
        # Remove non-ASCII characters because pyautogui may raise an error.
        strTemp = "".join(char for char in strTemp if char.isascii())
        strFileNamePrefix = _sanitize_filename(filename=strTemp) or "window"
        strNewFileName = (
            strFileNamePrefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        )
        Log.debug(strNewFileName)
        shutil.move(
            src=PATH_SCREENSHOT_DOCUMENTS / STR_SCREENSHOT_TEMP_NAME,
            dst=PATH_SCREENSHOT_DOCUMENTS / strNewFileName,
        )

        strGrayscale: Literal["true", "false"] = "true" if grayscale else "false"
        selector: SelectorImage = ensure_selector_image({
            "window": ensure_selector_window(
                _UiElement.get_control_selector(control=elementWindow)
            )["window"],
            "category": "image",
            "specification": [
                {
                    "FileName": strNewFileName,
                    "Grayscale": strGrayscale,
                    "Confidence": str(confidence),
                }
            ],
        })

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

    preview = _screenshot_to_base64(
        x=int(dictSecondaryAttr["secondary-x"]),
        y=int(dictSecondaryAttr["secondary-y"]),
        width=int(dictSecondaryAttr["secondary-width"]),
        height=int(dictSecondaryAttr["secondary-height"]),
    )

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
    }
    # Log.debug(dictReturn)
    # preview is so long, not print it.
    Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
    return dictReturn


@Log.trace()
def indicate_window(indicateDelaySeconds: int = 1) -> DictUiAnalyzerIndicateResult | None:
    threadHook: threading.Thread | None = None
    try:
        with uiautomation.UIAutomationInitializerInThread():
            _delay(indicateDelaySeconds)
            deadline = _create_deadline()
            threadHook = _start_hook()
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

                    control = uiautomation.ControlFromPoint(
                        x=dictCoordinate["x"], y=dictCoordinate["y"]
                    )

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
                    _wait_for_next_indicate_refresh(deadline)
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
                _wait_for_next_indicate_refresh(deadline)

            if _Hook.check_ESC_pressed():
                Log.debug("Pressed ESC, return None.")
                return None

            dictCoordinate = _get_mouse_selection_position(
                deadline=deadline,
                indicateName="indicate_window",
            )

            # Resolve the window again at the exact mouse-down position after the complete click has been suppressed.
            _close_indicate_overlay()
            element, tupleElementRectangle = _get_window_element_at_position(
                dictCoordinate=dictCoordinate
            )
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
            dictSecondaryAttr = get_control_secondary_attr(
                control=element,
                rectangle=tupleElementRectangle,
            )

        dictReturn: DictUiAnalyzerIndicateResult = {
            "selector": selector,
            "attributes": dictSecondaryAttr,
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
def validate(selector: Selector, timeout: int) -> dict[str, bool]:
    try:
        validate_selector(selector=selector)

        if selector.get("category") != "image":
            highlight(
                selector=selector,
                color="red",
                duration=2000,
                timeout=timeout * 1000,
                preDelay=0,
                postDelay=0,
            )
        else:
            """If use highlight() directly, image file will be moved to LiberRPALocalServer/screenshot. So create a function similar with _UiElement.get_element but not move file."""
            from liberrpa.UI._TerminableThread import timeout_kill_thread

            timeout = _UiElement.check_set_timeout(timeout=timeout * 1000)

            selectorTemp: SelectorImage = ensure_selector_image(selector)

            _, dictTarget = timeout_kill_thread(timeout=timeout)(_get_image_element)(
                selectorTemp
            )
            create_overlay(
                x=int(dictTarget["secondary-x"]),
                y=int(dictTarget["secondary-y"]),
                width=int(dictTarget["secondary-width"]),
                height=int(dictTarget["secondary-height"]),
                color="red",
                duration=2000,
            )
    except Exception as e:
        # Timeout or didn't find target element.
        Log.exception_info(e)
        return {"validate": False}
    else:
        # Highlight success.
        return {"validate": True}


def _get_mouse_selection_position(
    *,
    deadline: float,
    indicateName: str,
) -> DictPosition:
    tupleMousePosition = _Hook.get_mouse_left_position()
    if tupleMousePosition is None:
        raise UiElementNotFoundError("The mouse selection position was not captured.")

    floatRemainingSeconds = deadline - time.monotonic()
    if floatRemainingSeconds <= 0 or not _Hook.wait_mouse_left_released(
        timeout=floatRemainingSeconds
    ):
        _raise_indicate_timeout(f"{indicateName} mouse release")

    return {
        "x": tupleMousePosition[0],
        "y": tupleMousePosition[1],
    }


def _get_uia_element_at_position(
    *,
    dictCoordinate: DictPosition,
    retryCount: int = 3,
) -> tuple[uiautomation.Control, tuple[int, int, int, int], str]:
    exceptionLast: Exception | None = None

    for intAttempt in range(retryCount):
        try:
            control = uiautomation.ControlFromPoint(
                x=dictCoordinate["x"],
                y=dictCoordinate["y"],
            )
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
    control = uiautomation.ControlFromPoint(
        x=dictCoordinate["x"],
        y=dictCoordinate["y"],
    )
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


def _delay(indicateDelaySeconds: int) -> None:
    if indicateDelaySeconds > 0:
        delay(indicateDelaySeconds * 1000)


def _start_hook() -> threading.Thread:
    _Hook.subscribe_mouse_left()
    _Hook.subscribe_esc()
    threadHook = threading.Thread(target=_Hook.hook_in_another_thread, daemon=True)
    threadHook.start()
    time.sleep(0.01)
    return threadHook


def _stop_hook_thread(
    threadHook: threading.Thread | None,
    source: str,
) -> None:
    Log.debug("Clean up hook thread.")

    if threadHook is None or not threadHook.is_alive():
        Log.debug("threadHook has gone.")
        return

    Log.debug("Requesting the hook thread to stop.")
    _Hook.request_stop(source=source)
    threadHook.join(timeout=2)

    if threadHook.is_alive():
        Log.error("The hook thread did not terminate in time. Continuing anyway.")
    else:
        Log.debug("Successfully joined the hook thread.")


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
