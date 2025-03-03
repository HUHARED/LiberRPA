# FileName: _Chrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import (
    DictHtmlAttr,
    DictSpecHtml,
    ChromeDownloadItem,
    MouseButton,
    ClickMode,
    DictElementTreeItem,
)
from liberrpa.Common._WebSocket import send_command
from liberrpa.UI._CommonValue import boolHighlightUi
from liberrpa.UI._Overlay import create_overlay

from typing import Any, Literal


@Log.trace()
def get_download_list(limit: int = 5, timeout: int = 10000) -> list[ChromeDownloadItem]:
    dictCommand: dict[str, Any] = {"commandName": "getDownloadList", "timeout": timeout, "limit": limit}
    result: list[ChromeDownloadItem] = send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)
    return result


def get_element_attr_by_coordinates(
    x: int, y: int, usePath: bool = True
) -> tuple[list[DictHtmlAttr], tuple[list[DictElementTreeItem], list[int], int]]:
    dictCommand: dict[str, Any] = {"commandName": "getElementAttrByCoordinates", "x": x, "y": y, "usePath": usePath}
    result: tuple[list[DictHtmlAttr], tuple[list[DictElementTreeItem], list[int], int]] = send_command(
        eventName="chrome_command", command=dictCommand
    )
    return result


def get_element_attr_by_selector(htmlSelector: list[DictSpecHtml]) -> DictHtmlAttr:
    dictCommand: dict[str, Any] = {"commandName": "getElementAttrBySelector", "htmlSelector": htmlSelector}
    result: DictHtmlAttr = send_command(eventName="chrome_command", command=dictCommand)
    return result


def click_mouse_event(
    htmlSelector: list[DictSpecHtml],
    button: MouseButton = "left",
    clickMode: ClickMode = "single_click",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "clickMouseEvent",
        "htmlSelector": htmlSelector,
        "button": button,
        "clickMode": clickMode,
        "pressCtrl": pressCtrl,
        "pressShift": pressShift,
        "pressAlt": pressAlt,
        "pressWin": pressWin,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def set_element_text(
    htmlSelector: list[DictSpecHtml],
    text: str,
    emptyOriginalText: bool = False,
    validateWrittenText: bool = False,
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setElementText",
        "htmlSelector": htmlSelector,
        "text": text,
        "emptyOriginalText": emptyOriginalText,
        "validateWrittenText": validateWrittenText,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def focus_element(
    htmlSelector: list[DictSpecHtml],
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "focusElement",
        "htmlSelector": htmlSelector,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def get_parent_element_attr(
    htmlSelector: list[DictSpecHtml],
    upwardLevel: int = 1,
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> list[DictSpecHtml]:
    global boolHighlightUi

    dictCommand: dict[str, Any] = {
        "commandName": "getParentElementAttr",
        "htmlSelector": htmlSelector,
        "upwardLevel": upwardLevel,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    dictParentAttr: DictHtmlAttr = send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)
    if boolHighlightUi:
        create_overlay(
            int(dictParentAttr["secondary-x"]),
            int(dictParentAttr["secondary-y"]),
            int(dictParentAttr["secondary-width"]),
            int(dictParentAttr["secondary-height"]),
            color="red",
            duration=200,
            label=dictParentAttr["tagName"],  # type: ignore - It must have tagName when get its attributes.
        )
    dictToAppend: DictSpecHtml = {}  # type: ignore
    for strKey in dictParentAttr:
        if not strKey.startswith("secondary-"):
            dictToAppend[strKey] = dictParentAttr[strKey]
    listSpecification: list[DictSpecHtml] = [dictToAppend]
    return listSpecification


def get_children_element_attr(
    htmlSelector: list[DictSpecHtml],
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> list[DictSpecHtml]:
    global boolHighlightUi

    dictCommand: dict[str, Any] = {
        "commandName": "getChildrenElementAttr",
        "htmlSelector": htmlSelector,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    listChildrenAttr: list[DictHtmlAttr] = send_command(
        eventName="chrome_command", command=dictCommand, timeout=timeout
    )
    listSpecification: list[DictSpecHtml] = []
    for dictAttr in listChildrenAttr:
        if boolHighlightUi:
            create_overlay(
                int(dictAttr["secondary-x"]),
                int(dictAttr["secondary-y"]),
                int(dictAttr["secondary-width"]),
                int(dictAttr["secondary-height"]),
                color="red",
                duration=200,
                label=dictAttr["tagName"],  # type: ignore - It must have tagName when get its attributes.
            )

        dictToAppend: DictSpecHtml = {}  # type: ignore
        for strKey in dictAttr:
            if not strKey.startswith("secondary-"):
                dictToAppend[strKey] = dictAttr[strKey]
        listSpecification.append(dictToAppend)
    return listSpecification


def set_check_state(
    htmlSelector: list[DictSpecHtml],
    checkAction: Literal["checked", "unchecked", "toggle"] = "checked",
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setCheckState",
        "checkAction": checkAction,
        "htmlSelector": htmlSelector,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def get_selection(
    htmlSelector: list[DictSpecHtml],
    selectionType: Literal["text", "value", "index"] = "text",
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> str | int:
    dictCommand: dict[str, Any] = {
        "commandName": "getSelection",
        "htmlSelector": htmlSelector,
        "selectionType": selectionType,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    result: str | int = send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)
    return result


def set_selection(
    htmlSelector: list[DictSpecHtml],
    text: str | None = None,
    value: str | None = None,
    index: int | None = None,
    preExecutionDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setSelection",
        "htmlSelector": htmlSelector,
        "text": text,
        "value": value,
        "index": index,
        "preExecutionDelay": preExecutionDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


if __name__ == "__main__":
    # dictCommand: dict[str, Any] = {"commandName": "getDownloadList", "timeout": 10000, "limit": 5}
    # dictCommand: dict[str, Any] = {"commandName": "test", "x": 400, "y": 600, "usePath": True}
    # listSelector = [
    #     {
    #         "tagName": "a",
    #         "href": "./assets/rpaStockMarket/index.html",
    #         "directText": "RPA Stock Market",
    #         "isLeaf": "true",
    #         "path-regex": "html>body>app-root>div>nav>div>ul>li:nth-child.*>a",
    #     },
    # ]
    # dictCommand: dict[str, Any] = {
    #     "commandName": "clickElement",
    #     "htmlSelector": listSelector,
    #     "button": "left",
    #     "clickMode": "single_click",
    #     "executionMode": "simulate",
    #     "pressCtrl": False,
    #     "pressShift": False,
    #     "pressAlt": False,
    #     "pressWin": False,
    #     "timeout": 10000,
    # }
    # dictCommand: dict[str, Any] = {"commandName": "getElementAttrByCoordinates", "x": 900, "y": 155, "usePath": True}

    # result = _send_chrome_command(dictCommand)
    # print(result)

    # if result is not None:
    #     for dictTemp in result:
    #         create_overlay(x=int(dictTemp["secondary-x"]), y=int(dictTemp["secondary-y"]), width=int(dictTemp["secondary-width"]), height=int(dictTemp["secondary-height"]), color="red", duration=200)

    # print(get_download_list(limit=5))

    temp = get_element_attr_by_coordinates(x=900, y=155, usePath=False)
    with open("./project.json", mode="w") as fileObj:
        fileObj.write(str(temp[1]))

    """ htmlSelector: list[DictSpecHtml] = [
        {
            "tagName": "a",
            "href": "./assets/rpaStockMarket/index.html",
            "isHidden": "false",
            "isDisplayedNone": "false",
            "innerText": "RPA Stock Market",
            "directText": "RPA Stock Market",
            "isLeaf": "true",
        }
    ] """
    # print(get_element_attr_by_selector(htmlSelector=htmlSelector))
    # print(get_parent_element_attr(htmlSelector=htmlSelector))

    """ htmlSelector: list[DictSpecHtml] = [
        {
            "tagName": "textarea",
            "name": "q",
            "aria-label-regex": "搜.|search",
            "isLeaf": "true",
        }
    ]

    focus_element(htmlSelector) """
