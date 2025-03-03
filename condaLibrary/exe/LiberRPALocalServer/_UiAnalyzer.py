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
from liberrpa.UI._Screenshot import SCREENSHOT_DOCUMENTS_PATH, SCREENSHOT_TEMP_NAME, create_screenshot_manually
from liberrpa.UI._Image import find_image
from liberrpa.Mouse import get_mouse_position
from liberrpa.Dialog import show_notification
from liberrpa.Common._TypedValue import (
    DictForUiAnalyzer,
    DictHtmlAttr,
    # DictSpecHtmlOriginal,
    DictSpecHtml,
    DictSepcImage,
    DictHtmlSecondaryAttr,
    DictImageAttr,
    # SelectorWindowOriginal,
    SelectorWindow,
    # SelectorUiaOriginal,
    SelectorUia,
    # SelectorHtmlOriginal,
    SelectorHtml,
    SelectorImage,
    DictPosition,
    DictElementTreeItem,
)
from liberrpa.Common._Exception import UiElementNotFoundError
from liberrpa.Common._Chrome import get_element_attr_by_coordinates
import exe.LiberRPALocalServer._Hook as _Hook

import uiautomation
import threading
import time
from datetime import datetime
import os
import shutil
from pathvalidate import sanitize_filename as _sanitize_filename
import mss
import io
import base64
from PIL import Image

HIGHLIGHT_DURATION = 500


@Log.trace()
def indicate_uia(indicateDelaySeconds: int = 1) -> tuple[DictForUiAnalyzer, uiautomation.Control] | tuple[None, None]:

    global HIGHLIGHT_DURATION
    try:
        _delay(indicateDelaySeconds)
        threadHook = _start_hook()

        # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
        while _Hook.check_key_not_press():
            # The inner loop for get the element be hovered.
            while True:
                try:
                    dictCoordinate = get_mouse_position()
                    with uiautomation.UIAutomationInitializerInThread():
                        Log.debug("--get element--" + str(dictCoordinate))
                        element = uiautomation.ControlFromPoint(x=dictCoordinate["x"], y=dictCoordinate["y"])
                        Log.debug("--get element done--" + str(element))
                except Exception as e:
                    strError = (
                        f"Error to get UI element at {dictCoordinate}. If the error persists, you may need to restart LiberRPA Local Server, then try to find another element in the window, then locate the target element by Element Tree, or try to indicate an image instead of uia element.\n"
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(title="UI Analyzer Error", message=strError, duration=5, wait=True)
                    raise e
                else:
                    break

            Log.debug("Check Name")
            # Only need the element has "Name"
            try:
                while element is not None:
                    if getattr(element, "Name"):
                        Log.debug("Have Name(getattr).")
                        break
                    else:
                        Log.debug("Have no Name.")
                        element = element.GetParentControl()
                        Log.debug(f"Parent: {element}")
            except Exception as e:
                # If it is running in LiberRPA Local Server, some element may not useable when getattr(element, "Name"), like MenuItemControl in notepad.exe, I don't know why. But it can be handle by find another element in the windin, then locate the target element by Element Tree.
                strError = (
                    f"Error to get UI element at {dictCoordinate}. If the error persists, you may need to restart LiberRPA Local Server, then try to find another element in the window, then locate the target element by Element Tree, or try to indicate an image instead of uia element.\n"
                    + str(e)
                )
                Log.error(strError)
                show_notification(title="UI Analyzer Error", message=strError, duration=5, wait=True)
                raise e

            """ # Only need the element has "Name"
            while element is not None:
                if getattr(element, "Name"):
                    break
                else:
                    element = element.GetParentControl() """

            if element is None:
                raise UiElementNotFoundError("(!!!It should not appear.) Didn't find an element from cursor.")

            # Highlight it for checking.
            create_overlay(
                element.BoundingRectangle.left,
                element.BoundingRectangle.top,
                element.BoundingRectangle.width(),
                element.BoundingRectangle.height(),
                color="red",
                duration=HIGHLIGHT_DURATION,
                label=element.ControlTypeName,
            )

        if _Hook.check_ESC_pressed():
            Log.debug("Pressed ESC, return None.")
            return (None, None)

        # Mouse left pressed.
        Log.debug("Pressed mouse left.")

        # Get the selector(contains primary attributes) and secondary attributes.
        selector: SelectorUia = _UiElement.get_control_selector(control=element)  # type: ignore - it will return SelectorUia
        dictSecondaryAttr = get_control_secondary_attr(control=element)

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )

        dictReturn: DictForUiAnalyzer = {"selector": selector, "attributes": dictSecondaryAttr, "preview": preview}
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
        return dictReturn, element

    # except Exception as e:
    #     Log.exception_info(e)
    #     raise e

    finally:
        Log.critical("Finnally?")
        if "threadHook" in locals() and threadHook.is_alive():
            Log.critical("Trying to unhook and join the thread.")
            _Hook.unhook(source="indicate_uia")
            threadHook.join(timeout=2)
            if threadHook.is_alive():
                Log.error("Thread hook did not terminate in time. Continuing anyway.")
            else:
                Log.debug("Successfully joined the hook thread.")
        """ Log.critical("Finnally?")
        _Hook.unhook(source="indicate_uia")
        threadHook.join()
        Log.debug("End finally.")
        Log.debug(dictReturn) """


@Log.trace()
def indicate_chrome(
    indicateDelaySeconds: int = 1, usePath: bool = True
) -> tuple[DictForUiAnalyzer, tuple[list[DictElementTreeItem], list[int], int]] | None:

    global HIGHLIGHT_DURATION
    try:
        _delay(indicateDelaySeconds)
        threadHook = _start_hook()

        # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
        listAllAttr: list[DictHtmlAttr] = []
        while _Hook.check_key_not_press():
            # The inner loop for get the element be hovered.
            while True:
                try:
                    dictCoordinate = get_mouse_position()
                    # Call Chrome
                    # listAllAttr: list[DictHtmlAttr],
                    listAllAttr, tupleEleTree = get_element_attr_by_coordinates(
                        x=dictCoordinate["x"], y=dictCoordinate["y"], usePath=usePath
                    )
                    dictSecondaryAttr: DictHtmlSecondaryAttr = {
                        "secondary-x": listAllAttr[-1]["secondary-x"],
                        "secondary-y": listAllAttr[-1]["secondary-y"],
                        "secondary-width": listAllAttr[-1]["secondary-width"],
                        "secondary-height": listAllAttr[-1]["secondary-height"],
                    }

                    # Highlight the last element in the list.
                    create_overlay(
                        int(dictSecondaryAttr["secondary-x"]),
                        int(dictSecondaryAttr["secondary-y"]),
                        int(dictSecondaryAttr["secondary-width"]),
                        int(dictSecondaryAttr["secondary-height"]),
                        color="red",
                        duration=HIGHLIGHT_DURATION,
                        label=f"<{listAllAttr[-1].get("tagName", "")}> {listAllAttr[-1].get("id", "")} {listAllAttr[-1].get("name", "")}",
                    )

                except Exception as e:
                    strError = (
                        f"Error to get UI element at {dictCoordinate}. If the error persists, you may need to restart LiberRPA Local Server, restart Chrome, or try to indicate an image.\n"
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(title="UI Analyzer Error", message=strError, duration=5, wait=True)
                    raise e
                else:
                    break

        # After click, get the window element once.
        elementWindow = _get_window_element(dictCoordinate=dictCoordinate)

        if _Hook.check_ESC_pressed():
            Log.debug("Pressed ESC, return None.")
            return None

        # Mouse left pressed.
        Log.debug("Pressed mouse left.")

        # Delete all secondary attributes in listAllAttr, assign it to listSpecification
        listSpecification: list[DictSpecHtml] = []
        for dictAttr in listAllAttr:
            dictToAppend: DictSpecHtml = {}  # type: ignore - add value later.
            for strKey in dictAttr:
                if not strKey.startswith("secondary-"):
                    dictToAppend[strKey] = dictAttr[strKey]
            listSpecification.append(dictToAppend)

        selector: SelectorHtml = {
            "window": _UiElement.get_control_selector(control=elementWindow)["window"],
            "category": "html",
            "specification": listSpecification,
        }

        preview = _screenshot_to_base64(
            x=int(dictSecondaryAttr["secondary-x"]),
            y=int(dictSecondaryAttr["secondary-y"]),
            width=int(dictSecondaryAttr["secondary-width"]),
            height=int(dictSecondaryAttr["secondary-height"]),
        )

        dictReturn: DictForUiAnalyzer = {"selector": selector, "attributes": dictSecondaryAttr, "preview": preview}
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
        return (dictReturn, tupleEleTree)

    finally:
        _Hook.unhook(source="indicate_chrome")
        threadHook.join()


@Log.trace()
def indicate_image(
    indicateDelaySeconds: int = 1, grayscale: bool = True, confidence: float = 0.9
) -> DictForUiAnalyzer | None:

    global HIGHLIGHT_DURATION
    try:
        _delay(indicateDelaySeconds)

        temp = create_screenshot_manually()
        if not temp:
            print("Quit indicating.")
            return None

        # After Screenshot, get window selector to generate  image selector
        dictCoordinate = get_mouse_position()
        # time.sleep(0.1)
        elementWindow = _get_window_element(dictCoordinate=dictCoordinate)
        print(elementWindow)

        # Rename the screenshot: window's name + datetime + .png
        # Remove some common part in it to make the name concise.
        print("_sanitize_filename")
        strTemp = elementWindow.Name.replace(" - Google Chrome", "")
        # Remove non-ASCII characters because pyautogui may raise an error.
        strTemp = "".join(char for char in strTemp if char.isascii())
        strNewFileName = _sanitize_filename(filename=strTemp) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        Log.debug(strNewFileName)
        os.path.abspath(
            shutil.move(
                src=os.path.join(SCREENSHOT_DOCUMENTS_PATH, SCREENSHOT_TEMP_NAME),
                dst=os.path.join(SCREENSHOT_DOCUMENTS_PATH, strNewFileName),
            )
        )

        print("get_control_selector")

        selector: SelectorImage = {
            "window": _UiElement.get_control_selector(control=elementWindow)["window"],
            "category": "image",
            "specification": [
                {
                    "FileName": strNewFileName,
                    "Grayscale": str(
                        grayscale
                    ).lower(),  # json.dumps(grayscale) will make it to be 'GrayScale': '"true"'
                    "Confidence": str(confidence),
                }
            ],
        }

        listDictImageAttr = find_image(
            fileName=strNewFileName,
            region=None,
            confidence=confidence,
            grayscale=grayscale,
            limit=1,
            moveFile=False,
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
            duration=HIGHLIGHT_DURATION,
        )

        dictReturn: DictForUiAnalyzer = {"selector": selector, "attributes": dictSecondaryAttr, "preview": preview}
        # Log.debug(dictReturn)
        # preview is so long, not print it.
        Log.debug({"selector": selector, "attributes": dictSecondaryAttr})
        return dictReturn

    finally:
        pass


@Log.trace()
def indicate_window(indicateDelaySeconds: int = 1) -> DictForUiAnalyzer | None:

    global HIGHLIGHT_DURATION
    try:
        _delay(indicateDelaySeconds)
        threadHook = _start_hook()

        # Press mouse button left to stop the loop, then return result. Or Press ESC to return None.
        while _Hook.check_key_not_press():
            while True:
                try:
                    dictCoordinate = get_mouse_position()
                    # Find the element under the cursor
                    # print("Get element.")
                    with uiautomation.UIAutomationInitializerInThread():
                        element = uiautomation.ControlFromPoint(
                            x=dictCoordinate["x"], y=dictCoordinate["y"]
                        ).GetTopLevelControl()  # type: ignore - It will not be None.
                except Exception as e:
                    strError = (
                        "Error to get window at {dictCoordinate}.Maybe LiberRPA Local Server have no permission for the window. "
                        + str(e)
                    )
                    Log.error(strError)
                    show_notification(title="UI Analyzer Error", message=strError, duration=2, wait=True)
                else:
                    break

            if element is None:
                raise UiElementNotFoundError("(!!!It should not appear.) Didn't find an element from cursor.")

            create_overlay(
                element.BoundingRectangle.left,
                element.BoundingRectangle.top,
                element.BoundingRectangle.width(),
                element.BoundingRectangle.height(),
                color="red",
                duration=HIGHLIGHT_DURATION,
            )

        # Only need the element has "Name"
        if not getattr(element, "Name"):
            raise UiElementNotFoundError("(!!!It should not appear.) The window element has no Name.")

        if _Hook.check_ESC_pressed():
            Log.debug("Pressed ESC, return None.")
            return None

        # Mouse left pressed.
        Log.debug("Pressed mouse left.")

        # Only need the element has "Name"
        if not getattr(element, "Name"):
            raise ValueError("The element doen't have 'Name' attribute.")

        selector: SelectorWindow = _UiElement.get_control_selector(control=element)
        dictSecondaryAttr = get_control_secondary_attr(control=element)
        dictReturn: DictForUiAnalyzer = {"selector": selector, "attributes": dictSecondaryAttr}
        Log.debug(dictReturn)
        return dictReturn

    finally:
        _Hook.unhook(source="indicate_window")
        threadHook.join()


@Log.trace()
def validate(selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage, timeout: int) -> dict[str, bool]:
    try:
        if selector.get("category") != "image":
            highlight(
                selector=selector,
                color="red",
                duration=2000,
                timeout=timeout * 1000,
                preExecutionDelay=0,
                postExecutionDelay=0,
            )
        else:
            """If use highlight() directly, image file will be moved to LiberRPALocalServer/screenshot. So create a function similar with _UiElement.get_element but not move file."""
            from liberrpa.UI._TerminableThread import timeout_kill_thread

            timeout = _UiElement.check_set_timeout(timeout=timeout * 1000)

            selectorTemp: SelectorImage = selector  # type: ignore - It is SelectorImage

            _, dictTarget = timeout_kill_thread(timeout=timeout)(_get_image_element)(selectorTemp)
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


def _get_window_element(dictCoordinate: DictPosition) -> uiautomation.Control:
    """Get and highlight the window of Chrome and Image element."""

    print(dictCoordinate)
    # After click, get the window element once.
    with uiautomation.UIAutomationInitializerInThread():
        elementWindow = uiautomation.ControlFromPoint(x=dictCoordinate["x"], y=dictCoordinate["y"]).GetTopLevelControl()  # type: ignore - It will not be None.

    print("elementWindow=", elementWindow)

    if elementWindow is None:
        raise UiElementNotFoundError("(!!!It should not appear.) Didn't find an window element from cursor.")

    # Only need the element has "Name"
    if not getattr(elementWindow, "Name"):
        raise UiElementNotFoundError("(!!!It should not appear.) The window element has no Name.")

    print("create_overlay in _get_window_element")
    # Highlight window.
    create_overlay(
        elementWindow.BoundingRectangle.left,
        elementWindow.BoundingRectangle.top,
        elementWindow.BoundingRectangle.width(),
        elementWindow.BoundingRectangle.height(),
        color="red",
        duration=HIGHLIGHT_DURATION,
    )
    print("elementWindow before return", elementWindow)

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
            imageTemp = imageTemp.resize((intNewWidth, intMaxHeight), Image.Resampling.LANCZOS)  # Resize proportionally

        # Create an in-memory bytes buffer
        imageByte = io.BytesIO()
        imageTemp.save(imageByte, format="PNG")  # Save image to the byte stream as PNG
        imageByte.seek(0)  # Move to the beginning of the stream

        # Encode this image as base64
        strBase64 = base64.b64encode(imageByte.getvalue()).decode("utf-8")
        print("Size of image:", strBase64.__len__())
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
                f"It should have only one dictionary in 'specification', but it has {len(selectorTemp["specification"])}"
            )
        imageSelector: DictSepcImage = selectorTemp["specification"][0]

        listDictImageAttr = find_image(
            fileName=imageSelector["FileName"],
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
            moveFile=False,
        )
        # The list's length has limited by Index, but it may not find enough image(0 or less than Index+1), so check it.
        if len(listDictImageAttr) < int(imageSelector.get("Index", "0")) + 1:
            raise UiElementNotFoundError(f"Not Found image element. selector's specification: {imageSelector}")
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
                duration=HIGHLIGHT_DURATION,
            )
