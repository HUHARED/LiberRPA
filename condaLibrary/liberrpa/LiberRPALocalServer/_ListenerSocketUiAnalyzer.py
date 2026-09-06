# FileName: _ListenerSocketUiAnalyzer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


print("=== import _ListenerSocketUiAnalyzer ===")
from liberrpa.Logging import Log
from liberrpa.Common._Exception import get_exception_info
from liberrpa.UI._SelectorValidation import ensure_selector
from liberrpa.UI._UiDict import DictPosition
from liberrpa.Common._Chrome import get_element_tree_by_coordinates

import liberrpa.LiberRPALocalServer._UiAnalyzer as _UiAnalyzer
import liberrpa.LiberRPALocalServer._ElementTree as _ElementTree
from liberrpa.LiberRPALocalServer._ServerInit import (
    ensure_client_type,
    get_client_id,
    sioServer,
)
from liberrpa.LiberRPALocalServer._Tray import change_tray_icon

import json
import math
import threading
from copy import deepcopy
from typing import Any, Literal, cast


UiAnalyzerOperationName = Literal[
    "indicate_uia",
    "indicate_chrome",
    "indicate_image",
    "indicate_window",
    "validate",
]
UiAnalyzerResultMessageType = Literal["operationResult", "elementTreeResult"]

_SET_OPERATION_NAME: set[str] = {
    "indicate_uia",
    "indicate_chrome",
    "indicate_image",
    "indicate_window",
    "validate",
}
_INT_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_DICT_EXPECTED_COMMAND_KEYS: dict[UiAnalyzerOperationName, frozenset[str]] = {
    "indicate_uia": frozenset({"operationId", "commandName", "intIndicateDelaySeconds"}),
    "indicate_chrome": frozenset({
        "operationId",
        "commandName",
        "intIndicateDelaySeconds",
        "usePath",
    }),
    "indicate_image": frozenset({
        "operationId",
        "commandName",
        "intIndicateDelaySeconds",
        "grayscale",
        "confidence",
    }),
    "indicate_window": frozenset({
        "operationId",
        "commandName",
        "intIndicateDelaySeconds",
    }),
    "validate": frozenset({
        "operationId",
        "commandName",
        "intMatchTimeoutSeconds",
        "selector",
    }),
}

# Make sure only one UI Analyzer command is handled at a time.
_lockHandleUiAnalyzer = threading.Lock()


def _load_command(message: object) -> dict[str, Any]:
    if not isinstance(message, str):
        raise ValueError("UI Analyzer command must be a JSON string.")

    dictCommand = json.loads(message)
    if not isinstance(dictCommand, dict):
        raise ValueError("UI Analyzer command must be a JSON object.")

    if not all(isinstance(key, str) for key in dictCommand):
        raise ValueError("UI Analyzer command keys must be strings.")

    return dictCommand


def _get_operation_id(dictCommand: dict[str, Any]) -> int:
    intOperationId = dictCommand.get("operationId")
    if (
        type(intOperationId) is not int
        or intOperationId <= 0
        or intOperationId > _INT_MAX_SAFE_INTEGER
    ):
        raise ValueError(
            f"Invalid UI Analyzer operationId: {intOperationId!r}. "
            "Expected a positive JavaScript safe integer."
        )

    return intOperationId


def _get_operation_name(dictCommand: dict[str, Any]) -> UiAnalyzerOperationName:
    strOperationName = dictCommand.get("commandName")
    if (
        not isinstance(strOperationName, str)
        or strOperationName not in _SET_OPERATION_NAME
    ):
        raise ValueError(f"Invalid UI Analyzer commandName: {strOperationName!r}.")

    return cast(UiAnalyzerOperationName, strOperationName)


def _validate_command_keys(
    dictCommand: dict[str, Any],
    strOperationName: UiAnalyzerOperationName,
) -> None:
    setExpectedKeys = _DICT_EXPECTED_COMMAND_KEYS[strOperationName]
    setActualKeys = set(dictCommand)
    listMissingKeys = sorted(setExpectedKeys - setActualKeys)
    listUnexpectedKeys = sorted(setActualKeys - setExpectedKeys)

    if not listMissingKeys and not listUnexpectedKeys:
        return None

    listDetail: list[str] = []
    if listMissingKeys:
        listDetail.append(f"missing keys: {listMissingKeys}")
    if listUnexpectedKeys:
        listDetail.append(f"unexpected keys: {listUnexpectedKeys}")

    raise ValueError(
        f"Invalid fields for UI Analyzer command {strOperationName!r}: "
        + "; ".join(listDetail)
    )


def _get_indicate_delay(dictCommand: dict[str, Any]) -> int:
    intIndicateDelay = dictCommand.get("intIndicateDelaySeconds")
    if type(intIndicateDelay) is not int or not 1 <= intIndicateDelay <= 10:
        raise ValueError(
            f"Invalid UI Analyzer indicate delay: {intIndicateDelay!r}. Expected an integer from 1 to 10."
        )

    return intIndicateDelay


def _get_match_timeout(dictCommand: dict[str, Any]) -> int:
    intMatchTimeout = dictCommand.get("intMatchTimeoutSeconds")
    if type(intMatchTimeout) is not int or not 3 <= intMatchTimeout <= 60:
        raise ValueError(
            f"Invalid UI Analyzer match timeout: {intMatchTimeout!r}. Expected an integer from 3 to 60."
        )

    return intMatchTimeout


def _get_bool_argument(dictCommand: dict[str, Any], strArgumentName: str) -> bool:
    boolValue = dictCommand.get(strArgumentName)
    if type(boolValue) is not bool:
        raise ValueError(
            f"Invalid UI Analyzer {strArgumentName}: {boolValue!r}. Expected a boolean."
        )

    return boolValue


def _get_confidence(dictCommand: dict[str, Any]) -> float:
    confidence = dictCommand.get("confidence")

    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError(
            f"Invalid UI Analyzer confidence: {confidence!r}. Expected a number from 0.1 to 0.999."
        )

    floatConfidence = float(confidence)
    if not math.isfinite(floatConfidence) or not 0.1 <= floatConfidence <= 0.999:
        raise ValueError(
            f"Invalid UI Analyzer confidence: {confidence!r}. Expected a number from 0.1 to 0.999."
        )

    return floatConfidence


def _validate_command_arguments(
    dictCommand: dict[str, Any],
    strOperationName: UiAnalyzerOperationName,
) -> None:
    _validate_command_keys(dictCommand=dictCommand, strOperationName=strOperationName)

    match strOperationName:
        case "indicate_uia" | "indicate_window":
            _get_indicate_delay(dictCommand)

        case "indicate_chrome":
            _get_indicate_delay(dictCommand)
            _get_bool_argument(dictCommand, "usePath")

        case "indicate_image":
            _get_indicate_delay(dictCommand)
            _get_bool_argument(dictCommand, "grayscale")
            _get_confidence(dictCommand)

        case "validate":
            _get_match_timeout(dictCommand)
            ensure_selector(dictCommand.get("selector"))


def _emit_result(
    *,
    clientSid: str,
    intOperationId: int,
    messageType: UiAnalyzerResultMessageType,
    boolSuccess: bool,
    resultData: Any,
) -> None:
    dictMessage = {
        "operationId": intOperationId,
        "messageType": messageType,
        "boolSuccess": boolSuccess,
        "data": resultData,
    }
    sioServer.emit(
        "message_flask_to_uianalyzer",
        json.dumps(dictMessage),
        to=clientSid,
    )


def _emit_completed(*, clientSid: str, intOperationId: int) -> None:
    sioServer.emit(
        "message_flask_to_uianalyzer",
        json.dumps({
            "operationId": intOperationId,
            "messageType": "operationCompleted",
        }),
        to=clientSid,
    )


def _log_operation_result(*, boolSuccess: bool, resultData: Any) -> None:
    dictResult = {"boolSuccess": boolSuccess, "data": resultData}

    if not boolSuccess:
        Log.error(dictResult)
        return None

    # Preview images are too large to write to the diagnostic log.
    if isinstance(resultData, dict) and resultData.get("preview") is not None:
        dictResultTemp = deepcopy(dictResult)
        dictDataTemp = dictResultTemp.get("data")
        if isinstance(dictDataTemp, dict):
            dictDataTemp.pop("preview", None)
        Log.debug(dictResultTemp)
    else:
        Log.info(dictResult)


def _send_rejected_operation(
    *,
    clientSid: str,
    intOperationId: int,
    strMessage: str,
) -> None:
    _emit_result(
        clientSid=clientSid,
        intOperationId=intOperationId,
        messageType="operationResult",
        boolSuccess=False,
        resultData=strMessage,
    )
    _emit_completed(clientSid=clientSid, intOperationId=intOperationId)


@Log.trace()
@sioServer.on("uianalyzer_command")
def handle_uianalyzer_command(message: object) -> None:
    clientSid = get_client_id()
    intOperationId: int | None = None

    try:
        ensure_client_type(expectedClientType="uiAnalyzer", clientSid=clientSid)
    except PermissionError as e:
        Log.warning(str(e))
        return None

    try:
        dictCommand = _load_command(message)
        intOperationId = _get_operation_id(dictCommand)
        strOperationName = _get_operation_name(dictCommand)
        _validate_command_arguments(
            dictCommand=dictCommand,
            strOperationName=strOperationName,
        )
    except Exception as e:
        strError = "Error: " + str(get_exception_info(e))
        Log.error(strError)
        if intOperationId is not None:
            _send_rejected_operation(
                clientSid=clientSid,
                intOperationId=intOperationId,
                strMessage=strError,
            )
        return None

    Log.info(
        f"Received UI Analyzer operation: operationId={intOperationId}, "
        f"commandName={strOperationName}, SID={clientSid}"
    )

    if not _lockHandleUiAnalyzer.acquire(blocking=False):
        strError = "Error: Another UI Analyzer command is running."
        Log.debug(strError)
        _send_rejected_operation(
            clientSid=clientSid,
            intOperationId=intOperationId,
            strMessage=strError,
        )
        return None

    resultData: Any = None
    dictChromeCoordinate: DictPosition | None = None
    boolChromeUsePath: bool | None = None
    boolOperationSuccess = False

    try:
        change_tray_icon(component="LiberRPALocalServer_Indicating")

        match strOperationName:
            case "indicate_uia":
                Log.debug("_UiAnalyzer.indicate_uia")
                resultData = _UiAnalyzer.indicate_uia(_get_indicate_delay(dictCommand))

            case "indicate_chrome":
                boolChromeUsePath = _get_bool_argument(dictCommand, "usePath")
                tupleChromeResult = _UiAnalyzer.indicate_chrome(
                    _get_indicate_delay(dictCommand),
                    boolChromeUsePath,
                )
                if tupleChromeResult is not None:
                    resultData, dictChromeCoordinate = tupleChromeResult

            case "indicate_image":
                resultData = _UiAnalyzer.indicate_image(
                    indicateDelaySeconds=_get_indicate_delay(dictCommand),
                    grayscale=_get_bool_argument(dictCommand, "grayscale"),
                    confidence=_get_confidence(dictCommand),
                )

            case "indicate_window":
                resultData = _UiAnalyzer.indicate_window(_get_indicate_delay(dictCommand))

            case "validate":
                resultData = _UiAnalyzer.validate(
                    ensure_selector(dictCommand.get("selector")),
                    _get_match_timeout(dictCommand),
                )

        boolOperationSuccess = True

    except Exception as e:
        resultData = "Error: " + str(get_exception_info(e))

    try:
        _log_operation_result(boolSuccess=boolOperationSuccess, resultData=resultData)
        _emit_result(
            clientSid=clientSid,
            intOperationId=intOperationId,
            messageType="operationResult",
            boolSuccess=boolOperationSuccess,
            resultData=resultData,
        )

        # Generate Element Tree.
        if boolOperationSuccess and isinstance(resultData, dict):
            if strOperationName == "indicate_uia":
                Log.debug("Get UIA Element Tree.")
                try:
                    tupleEleTreeUia = _ElementTree.generate_control_tree_by_selector(
                        selector=resultData["selector"]
                    )
                except Exception as e:
                    strTreeError = "Error: Failed to generate UIA Element Tree. " + str(
                        get_exception_info(e)
                    )
                    Log.error(strTreeError)
                    _emit_result(
                        clientSid=clientSid,
                        intOperationId=intOperationId,
                        messageType="elementTreeResult",
                        boolSuccess=False,
                        resultData=strTreeError,
                    )
                else:
                    _emit_result(
                        clientSid=clientSid,
                        intOperationId=intOperationId,
                        messageType="elementTreeResult",
                        boolSuccess=True,
                        resultData=tupleEleTreeUia,
                    )

            elif strOperationName == "indicate_chrome":
                Log.debug("Get HTML Element Tree.")
                if dictChromeCoordinate is None or boolChromeUsePath is None:
                    strTreeError = "Error: Missing the selected HTML element position."
                    Log.error(strTreeError)
                    _emit_result(
                        clientSid=clientSid,
                        intOperationId=intOperationId,
                        messageType="elementTreeResult",
                        boolSuccess=False,
                        resultData=strTreeError,
                    )
                else:
                    try:
                        tupleEleTree = get_element_tree_by_coordinates(
                            x=dictChromeCoordinate["x"],
                            y=dictChromeCoordinate["y"],
                            usePath=boolChromeUsePath,
                        )
                    except Exception as e:
                        strTreeError = (
                            "Error: Failed to generate HTML Element Tree. "
                            + str(get_exception_info(e))
                        )
                        Log.error(strTreeError)
                        _emit_result(
                            clientSid=clientSid,
                            intOperationId=intOperationId,
                            messageType="elementTreeResult",
                            boolSuccess=False,
                            resultData=strTreeError,
                        )
                    else:
                        _emit_result(
                            clientSid=clientSid,
                            intOperationId=intOperationId,
                            messageType="elementTreeResult",
                            boolSuccess=True,
                            resultData=tupleEleTree,
                        )
    except Exception as e:
        Log.error(get_exception_info(e))
    finally:
        try:
            change_tray_icon(component="LiberRPALocalServer")
        except Exception as e:
            Log.error(get_exception_info(e))

        _lockHandleUiAnalyzer.release()

        try:
            _emit_completed(clientSid=clientSid, intOperationId=intOperationId)
        except Exception as e:
            Log.error(get_exception_info(e))
