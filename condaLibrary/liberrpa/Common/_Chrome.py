# FileName: _Chrome.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._TypedValue import (
    ChromeDownloadItem,
    MouseButton,
    ClickMode,
)
from liberrpa.UI._UiDict import (
    DictHtmlAttr,
    DictSpecHtml,
    DictElementTreeItem,
    DictHtmlSelectorRecommendationResult,
)
from liberrpa.Common._WebSocket import send_command
import liberrpa.UI._CommonValue as _CommonValue
from liberrpa.UI._Overlay import create_overlay

from typing import Any, Literal, cast


# Chrome should finish its 10-second bounded tree build before this Local Server fallback.
_HTML_ELEMENT_TREE_SERVER_TIMEOUT_MS = 12000
# The Python client must wait longer than the Local Server fallback, which adds its own response grace.
_HTML_ELEMENT_TREE_CLIENT_TIMEOUT_MS = 16000

type HtmlElementTreeResult = tuple[list[DictElementTreeItem], list[int], int]


def _ensure_html_attr_list(value: object) -> list[DictHtmlAttr]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("Chrome returned an invalid HTML attribute list.")

    return cast(list[DictHtmlAttr], value)


def _ensure_html_specification_list(value: object) -> list[DictSpecHtml]:
    if (
        not isinstance(value, list)
        or len(value) != 1
        or not all(
            isinstance(item, dict)
            and len(item) > 0
            and all(
                isinstance(key, str) and isinstance(itemValue, str)
                for key, itemValue in item.items()
            )
            for item in value
        )
    ):
        raise ValueError("Chrome returned an invalid recommended HTML specification.")

    return cast(list[DictSpecHtml], value)


def _ensure_html_selector_recommendation_result(
    value: object,
) -> DictHtmlSelectorRecommendationResult:
    if not isinstance(value, dict) or set(value) != {
        "allLayerAttributes",
        "recommendedSpecification",
    }:
        raise ValueError(
            "Chrome returned an invalid HTML selector recommendation result."
        )

    return {
        "allLayerAttributes": _ensure_html_attr_list(value["allLayerAttributes"]),
        "recommendedSpecification": _ensure_html_specification_list(
            value["recommendedSpecification"]
        ),
    }


def _ensure_html_element_tree_result(value: object) -> HtmlElementTreeResult:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("Chrome returned an invalid HTML Element Tree result.")

    listTree, listExpandedId, intActivatedId = value
    if not isinstance(listTree, list) or not all(
        isinstance(item, dict) for item in listTree
    ):
        raise ValueError("Chrome returned an invalid HTML Element Tree item list.")
    if not isinstance(listExpandedId, list) or not all(
        type(item) is int for item in listExpandedId
    ):
        raise ValueError("Chrome returned an invalid HTML Element Tree expanded ID list.")
    if type(intActivatedId) is not int:
        raise ValueError("Chrome returned an invalid HTML Element Tree activated ID.")

    return (
        cast(list[DictElementTreeItem], listTree),
        cast(list[int], listExpandedId),
        intActivatedId,
    )


def get_download_list(limit: int = 5, timeout: int = 10000) -> list[ChromeDownloadItem]:
    dictCommand: dict[str, Any] = {
        "commandName": "getDownloadList",
        "timeout": timeout,
        "limit": limit,
    }
    result: list[ChromeDownloadItem] = send_command(
        eventName="chrome_command", command=dictCommand, timeout=timeout
    )
    return result


def get_element_attr_by_coordinates(
    x: int, y: int, usePath: bool = True
) -> list[DictHtmlAttr]:
    dictCommand: dict[str, Any] = {
        "commandName": "getElementAttrByCoordinates",
        "x": x,
        "y": y,
        "usePath": usePath,
    }
    result: object = send_command(eventName="chrome_command", command=dictCommand)
    return _ensure_html_attr_list(result)


def get_element_selector_by_coordinates(
    x: int,
    y: int,
    usePath: bool = True,
) -> DictHtmlSelectorRecommendationResult:
    dictCommand: dict[str, Any] = {
        "commandName": "getElementSelectorByCoordinates",
        "x": x,
        "y": y,
        "usePath": usePath,
    }
    result: object = send_command(eventName="chrome_command", command=dictCommand)
    return _ensure_html_selector_recommendation_result(result)


def get_element_tree_by_coordinates(
    x: int,
    y: int,
    usePath: bool = True,
) -> HtmlElementTreeResult:
    dictCommand: dict[str, Any] = {
        "commandName": "getElementTreeByCoordinates",
        "x": x,
        "y": y,
        "usePath": usePath,
        "timeout": _HTML_ELEMENT_TREE_SERVER_TIMEOUT_MS,
    }
    result: object = send_command(
        eventName="chrome_command",
        command=dictCommand,
        timeout=_HTML_ELEMENT_TREE_CLIENT_TIMEOUT_MS,
    )
    return _ensure_html_element_tree_result(result)


def get_element_attr_by_selector(htmlSelector: list[DictSpecHtml]) -> DictHtmlAttr:
    dictCommand: dict[str, Any] = {
        "commandName": "getElementAttrBySelector",
        "htmlSelector": htmlSelector,
    }
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
    preDelay: int = 300,
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
        "preDelay": preDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def set_element_text(
    htmlSelector: list[DictSpecHtml],
    text: str,
    clearBeforeWrite: bool = False,
    validateText: bool = False,
    preDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setElementText",
        "htmlSelector": htmlSelector,
        "text": text,
        "clearBeforeWrite": clearBeforeWrite,
        "validateText": validateText,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def focus_element(
    htmlSelector: list[DictSpecHtml],
    preDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "focusElement",
        "htmlSelector": htmlSelector,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def get_parent_element_attr(
    htmlSelector: list[DictSpecHtml],
    upwardLevel: int = 1,
    preDelay: int = 300,
    timeout: int = 10000,
) -> list[DictSpecHtml]:

    dictCommand: dict[str, Any] = {
        "commandName": "getParentElementAttr",
        "htmlSelector": htmlSelector,
        "upwardLevel": upwardLevel,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    dictParentAttr: DictHtmlAttr = send_command(
        eventName="chrome_command", command=dictCommand, timeout=timeout
    )
    if _CommonValue.boolHighlightUi:
        strTagName = dictParentAttr.get("tagName")
        if not isinstance(strTagName, str) or not strTagName:
            raise ValueError(
                f"HTML attribute dictionary has no valid tagName: {dictParentAttr}"
            )

        create_overlay(
            int(dictParentAttr["secondary-x"]),
            int(dictParentAttr["secondary-y"]),
            int(dictParentAttr["secondary-width"]),
            int(dictParentAttr["secondary-height"]),
            color="red",
            duration=200,
            label=strTagName,
        )
    dictToAppendTemp: dict[str, Any] = {}

    for strKey in dictParentAttr:
        if not strKey.startswith("secondary-"):
            dictToAppendTemp[strKey] = dictParentAttr[strKey]

    listSpecification: list[DictSpecHtml] = [cast(DictSpecHtml, dictToAppendTemp)]
    return listSpecification


def get_children_element_attr(
    htmlSelector: list[DictSpecHtml],
    preDelay: int = 300,
    timeout: int = 10000,
) -> list[DictSpecHtml]:

    dictCommand: dict[str, Any] = {
        "commandName": "getChildrenElementAttr",
        "htmlSelector": htmlSelector,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    listChildrenAttr: list[DictHtmlAttr] = send_command(
        eventName="chrome_command", command=dictCommand, timeout=timeout
    )
    listSpecification: list[DictSpecHtml] = []
    for dictAttr in listChildrenAttr:
        if _CommonValue.boolHighlightUi:
            strTagName = dictAttr.get("tagName")
            if not isinstance(strTagName, str) or not strTagName:
                raise ValueError(
                    f"HTML attribute dictionary has no valid tagName: {dictAttr}"
                )

            create_overlay(
                int(dictAttr["secondary-x"]),
                int(dictAttr["secondary-y"]),
                int(dictAttr["secondary-width"]),
                int(dictAttr["secondary-height"]),
                color="red",
                duration=200,
                label=strTagName,
            )

        dictToAppendTemp: dict[str, Any] = {}

        for strKey in dictAttr:
            if not strKey.startswith("secondary-"):
                dictToAppendTemp[strKey] = dictAttr[strKey]

        listSpecification.append(cast(DictSpecHtml, dictToAppendTemp))
    return listSpecification


def set_check_state(
    htmlSelector: list[DictSpecHtml],
    checkAction: Literal["checked", "unchecked", "toggle"] = "checked",
    preDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setCheckState",
        "checkAction": checkAction,
        "htmlSelector": htmlSelector,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


def get_selection(
    htmlSelector: list[DictSpecHtml],
    selectionType: Literal["text", "value", "index"] = "text",
    preDelay: int = 300,
    timeout: int = 10000,
) -> str | int:
    dictCommand: dict[str, Any] = {
        "commandName": "getSelection",
        "htmlSelector": htmlSelector,
        "selectionType": selectionType,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    result: str | int = send_command(
        eventName="chrome_command", command=dictCommand, timeout=timeout
    )
    return result


def set_selection(
    htmlSelector: list[DictSpecHtml],
    text: str | None = None,
    value: str | None = None,
    index: int | None = None,
    preDelay: int = 300,
    timeout: int = 10000,
) -> None:
    dictCommand: dict[str, Any] = {
        "commandName": "setSelection",
        "htmlSelector": htmlSelector,
        "text": text,
        "value": value,
        "index": index,
        "preDelay": preDelay,
        "timeout": timeout,
    }
    send_command(eventName="chrome_command", command=dictCommand, timeout=timeout)


if __name__ == "__main__":
    pass
