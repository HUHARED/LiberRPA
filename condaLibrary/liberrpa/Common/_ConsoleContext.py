# FileName: _ConsoleContext.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
import json
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast
from urllib.parse import urlsplit


class ConsoleClientType(StrEnum):
    EDITOR = "editor"
    EXECUTOR = "executor"


@dataclass(frozen=True, slots=True)
class ConsoleContext:
    consoleUrl: str
    clientType: ConsoleClientType
    token: str = field(repr=False)


_STR_ENV_CONSOLE_PIPE = "LIBERRPA_CONSOLE_PIPE"
_STR_ENV_CONSOLE_HOST_PID = "LIBERRPA_CONSOLE_HOST_PID"
_STR_ENV_CONSOLE_CREDENTIAL_ID = "LIBERRPA_CONSOLE_CREDENTIAL_ID"
_CONSOLE_PIPE_PATTERN = re.compile(
    r"\\\\\.\\pipe\\LiberRPA-Console-(editor|executor)-[0-9a-f-]{36}"
)
_STR_CONTEXT_REQUEST_PREFIX = "LIBERRPA_CONSOLE_CONTEXT_V1 "
_INT_MAX_CONTEXT_BYTES = 16 * 1024
_INT_CONTACT_TIMEOUT_SECONDS = 3
# WinBase.h SECURITY_IDENTIFICATION; pywin32 does not expose it in win32con.
_INT_SECURITY_IDENTIFICATION = 0x00010000

_consoleContext: ConsoleContext | None = None
_boolInitialized = False
_strUnavailableMessage = "Console authentication has not been initialized."


def _read_host_context(pipePath: str, hostProcessId: int, credentialId: str) -> bytes:
    import win32con
    import win32file
    import win32pipe

    floatContactDeadline = time.monotonic() + _INT_CONTACT_TIMEOUT_SECONDS
    win32pipe.WaitNamedPipe(pipePath, _INT_CONTACT_TIMEOUT_SECONDS * 1000)
    pipeHandle = win32file.CreateFile(
        pipePath,
        win32con.GENERIC_READ | win32con.GENERIC_WRITE,
        0,
        None,
        win32con.OPEN_EXISTING,
        # The broker must not impersonate the Python process.
        win32con.SECURITY_SQOS_PRESENT | _INT_SECURITY_IDENTIFICATION,
        None,
    )
    try:
        intPipeHandle = int(pipeHandle)
        if win32pipe.GetNamedPipeServerProcessId(intPipeHandle) != hostProcessId:
            raise ValueError("The Console pipe belongs to a different host process.")

        # The host replies only after receiving this request.
        # Its default Windows pipe ACL permits writes by its owner, not by other ordinary users.
        win32file.WriteFile(
            intPipeHandle,
            f"{_STR_CONTEXT_REQUEST_PREFIX}{credentialId}\n".encode("ascii"),
        )
        responseBuffer = bytearray()
        while time.monotonic() < floatContactDeadline:
            _, intAvailableBytes, _ = win32pipe.PeekNamedPipe(intPipeHandle, 0)
            if intAvailableBytes == 0:
                time.sleep(0.01)
                continue
            _, responseChunkBytes = cast(
                tuple[int, bytes],
                win32file.ReadFile(
                    intPipeHandle,
                    min(
                        intAvailableBytes,
                        _INT_MAX_CONTEXT_BYTES + 1 - len(responseBuffer),
                    ),
                ),
            )
            responseBuffer.extend(responseChunkBytes)
            if len(responseBuffer) > _INT_MAX_CONTEXT_BYTES:
                raise ValueError("The Console host response is too large.")
            if b"\n" in responseBuffer:
                responseLineBytes, _, remainingResponseBytes = responseBuffer.partition(
                    b"\n"
                )
                if remainingResponseBytes:
                    raise ValueError("The Console host response is invalid.")
                return bytes(responseLineBytes)
        raise TimeoutError("The Console host did not respond in time.")
    finally:
        pipeHandle.Close()


def _parse_host_context(
    responseBytes: bytes, clientType: ConsoleClientType
) -> ConsoleContext | None:
    responseValue = json.loads(responseBytes)
    if not isinstance(responseValue, dict) or responseValue.get("version") != 1:
        raise ValueError("The Console host protocol is invalid.")

    if "context" not in responseValue:
        raise ValueError("The Console host response is incomplete.")

    contextValue = responseValue["context"]
    if contextValue is None:
        return None

    if not isinstance(contextValue, dict) or contextValue.get("clientType") != clientType:
        raise ValueError("The Console host identity is invalid.")

    strConsoleUrl = contextValue.get("consoleUrl")
    strToken = contextValue.get("token")
    if not isinstance(strConsoleUrl, str) or not isinstance(strToken, str):
        raise ValueError("The Console host identity is incomplete.")
    urlObj = urlsplit(strConsoleUrl)
    if (
        urlObj.scheme not in ("http", "https")
        or not urlObj.hostname
        or urlObj.username is not None
        or urlObj.password is not None
        or urlObj.path not in ("", "/")
        or urlObj.query
        or urlObj.fragment
    ):
        raise ValueError("The Console host address is invalid.")
    strTokenPrefix = (
        "liberrpa_editor_"
        if clientType == ConsoleClientType.EDITOR
        else "liberrpa_executor_"
    )
    if re.fullmatch(re.escape(strTokenPrefix) + r"[A-Za-z0-9_-]{43}", strToken) is None:
        raise ValueError("The Console host credential is invalid.")

    return ConsoleContext(strConsoleUrl.rstrip("/"), clientType, strToken)


def initialize_console_context() -> None:
    """Resolve launch credentials once and report their local availability."""
    global _consoleContext, _boolInitialized, _strUnavailableMessage

    if _boolInitialized:
        return
    _boolInitialized = True

    strPipePath = os.environ.get(_STR_ENV_CONSOLE_PIPE, "")
    if not strPipePath:
        _strUnavailableMessage = (
            "No Console host was available when liberrpa initialized. "
            "Sign in to Editor or Executor, then start a new Python run from that client. "
            "In VS Code, use a new terminal."
        )
        print("Console: No host available.", flush=True)
        return

    strCredentialId = os.environ.get(_STR_ENV_CONSOLE_CREDENTIAL_ID, "")
    if not strCredentialId:
        _strUnavailableMessage = (
            "No Console credentials were available in this process's launch environment. "
            "Sign in to the launching client, then start a new run or terminal."
        )
        print("Console: No credentials available at launch.", flush=True)
        return

    try:
        if re.fullmatch(r"[0-9a-f]{64}", strCredentialId) is None:
            raise ValueError("The launching Console credential identity is invalid.")

        pipePathMatch = _CONSOLE_PIPE_PATTERN.fullmatch(strPipePath)
        if os.name != "nt" or pipePathMatch is None:
            raise ValueError("The Console host pipe is invalid.")

        intHostProcessId = int(os.environ.get(_STR_ENV_CONSOLE_HOST_PID, "0"))
        if intHostProcessId <= 0:
            raise ValueError("The Console host process is missing.")

        _consoleContext = _parse_host_context(
            _read_host_context(strPipePath, intHostProcessId, strCredentialId),
            ConsoleClientType(pipePathMatch.group(1)),
        )
    except Exception:
        # Console setup must not prevent local automation from running.
        # pywintypes.error is not an OSError subclass.
        # Do not expose exception details: malformed IPC data could contain a token.
        _strUnavailableMessage = (
            "The launching client's Console identity could not be prepared. "
            "Check the client, then start a new Python run. "
            "In VS Code, use a new terminal after reloading the window."
        )
        print("Console: Credential initialization failed.", flush=True)
        return

    if _consoleContext is None:
        _strUnavailableMessage = (
            "The launching client's original Console identity is no longer available. "
            "Start a new run or terminal from the signed-in client."
        )
        print("Console: Launch credentials unavailable.", flush=True)
    else:
        print("Console: Credentials available.", flush=True)


def get_console_context() -> ConsoleContext:
    if _consoleContext is None:
        raise RuntimeError(_strUnavailableMessage)
    return _consoleContext
