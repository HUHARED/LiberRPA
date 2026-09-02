# FileName: Browser.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._Exception import ChromeCommandError
from liberrpa.UI._OperationLock import lock_ui_operation
from liberrpa.Common._TypedValue import (
    DictCookiesOfChrome,
    ChromeDownloadItem,
    JsonValue,
    StrPath,
)
from liberrpa.Common._Chrome import get_download_list as _get_download_list

from pathlib import Path
import time
import psutil
import os
import shutil
import winreg
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Literal, overload


_CHROME_APP_PATHS_REGISTRY_KEY = (
    R"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
)
_CHROME_RELATIVE_PATH = Path("Google") / "Chrome" / "Application" / "chrome.exe"


def _get_existing_file_path(path: StrPath | None) -> str | None:
    """Return the resolved path if *path* points to an existing file."""
    if path is None:
        return None

    pathString = (
        os.path.expandvars(os.path.expanduser(os.fspath(path))).strip().strip('"')
    )
    if not pathString:
        return None

    filePath = Path(pathString)
    try:
        if filePath.is_file():
            return str(filePath.resolve())
    except OSError:
        pass

    return None


def _get_chrome_from_app_paths() -> str | None:
    """Locate Chrome through Windows' App Paths registration."""
    # Chrome may be registered per-user or system-wide.
    # Explicitly check both 32-bit and 64-bit registry views so this also works when Python's bitness differs from Windows/Chrome's bitness.
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(
                    root,
                    _CHROME_APP_PATHS_REGISTRY_KEY,
                    0,
                    winreg.KEY_READ | view,
                ) as key:
                    value, _ = winreg.QueryValueEx(key, "")
            except OSError:
                continue

            if isinstance(value, str):
                chromePath = _get_existing_file_path(value)
                if chromePath:
                    return chromePath

    return None


def _get_chrome_from_default_paths() -> str | None:
    """Locate Chrome in the standard per-user and system-wide directories."""
    candidates: list[Path] = []

    for envName in ("LOCALAPPDATA", "PROGRAMW6432", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        basePath = os.environ.get(envName)
        if basePath:
            candidates.append(Path(basePath) / _CHROME_RELATIVE_PATH)

    checkedPaths: set[str] = set()
    for candidate in candidates:
        normalizedPath = os.path.normcase(os.fspath(candidate))
        if normalizedPath in checkedPaths:
            continue
        checkedPaths.add(normalizedPath)

        chromePath = _get_existing_file_path(candidate)
        if chromePath:
            return chromePath

    return None


def _find_chrome_path() -> str | None:
    """
    Locate Google Chrome without relying on an already running Chrome process.

    The lookup order is Windows App Paths, standard installation directories, and finally PATH. Keeping discovery independent of process state makes cold-start behavior deterministic.
    """
    chromePath = _get_chrome_from_app_paths()
    if chromePath:
        return chromePath

    chromePath = _get_chrome_from_default_paths()
    if chromePath:
        return chromePath

    chromePath = shutil.which("chrome.exe")
    if chromePath:
        return _get_existing_file_path(chromePath)

    return None


@dataclass
class BrowserObj:
    """
    Represents the browser capability used by LiberRPA.

    This object does not bind to a specific browser window or tab. Browser
    commands are sent to the active supported browser tab through the local
    LiberRPA browser bridge.
    """

    browserType: Literal["chrome"] = "chrome"
    path: str = ""
    socketId: str = ""

    def __str__(self) -> str:
        return f"BrowserObj(type: {self.browserType}, path: {self.path}, socketId: {self.socketId})"


@Log.trace()
@lock_ui_operation
def open_browser(
    browserType: Literal["chrome"] = "chrome",
    url: str = "about:blank",
    path: StrPath | None = None,
    params: str | list[str] = "",
    timeout: int = 30000,
) -> BrowserObj:
    """
    Open a browser to access the url.

    If the browser is running, it will open a new tab.

    Parameters:
        browserType: The type of browser to manipulate (currently only "chrome" is supported).
        url: The URL to open in the browser.
        path: The filesystem path to the browser exe. If not provided, Chrome is located automatically using Windows application registration, standard install directories, and PATH.
        params: Additional command-line parameters to pass when launching the browser.

            You can pass a string for simple cases, such as "--start-maximized".
            If a parameter value contains spaces, passing a list[str] is recommended,
            for example ["--user-data-dir=C:/Temp/Chrome Profile"].

            For Chrome, you can check all params in [List of Chromium Command Line Switches](https://peter.sh/experiments/chromium-command-line-switches/)
        timeout: Maximum time to wait until the browser's extension can communicate with LiberRPA Local Server, in milliseconds.

    Returns:
        BrowserObj: A handle indicating browser type and Chrome extension availability. Browser operations target the currently active common web page tab in the last focused browser window.

    """

    browserObj = BrowserObj()

    match browserType:
        case "chrome":
            browserObj.browserType = "chrome"

            if path is not None:
                chromePath = _get_existing_file_path(path)
                if chromePath:
                    browserObj.path = chromePath
                else:
                    raise FileNotFoundError(f"Could not find a file at '{path}'.")
            else:
                chromePath = _find_chrome_path()
                if chromePath:
                    browserObj.path = chromePath
                else:
                    raise FileNotFoundError(
                        "Could not locate Google Chrome automatically. "
                        "If Chrome is installed in a non-standard location, specify its executable path using the 'path' parameter. "
                        "You can also open it using Application.run_application() and then bind it using Browser.bind_browser()."
                    )

            dictCommand = {
                "commandName": "open_browser",
                "url": url,
                "path": browserObj.path,
                "params": params,
            }
            send_command(eventName="application_command", command=dictCommand)

            # Make sure Chrome extension is working.
            dictCommand = {"commandName": "get_chrome_socket_id"}
            timeStart = time.monotonic()
            while True:
                strSocketId = send_command(
                    eventName="application_command", command=dictCommand
                )
                if not strSocketId:
                    if (time.monotonic() - timeStart) * 1000 <= timeout:
                        time.sleep(0.5)
                        continue
                    else:
                        raise ChromeCommandError(
                            f"Can't access LiberRPA Chrome extension after {timeout} milliseconds, if Chrome is running, you should install LiberRPA Chrome extension and turn it on."
                        )
                else:
                    browserObj.socketId = strSocketId
                    break
            return browserObj

        case _:
            raise ValueError(f"This is not a supported browser type: '{browserType}'")


@Log.trace()
@lock_ui_operation
def bind_browser(browserType: Literal["chrome"] = "chrome") -> BrowserObj:
    """
    Bind a running browser.

    Parameters:
        browserType: The type of browser to manipulate (currently only "chrome" is supported).

    Returns:
        BrowserObj: A handle indicating browser type and Chrome extension availability. Browser operations target the currently active common web page tab in the last focused browser window.
    """
    browserObj = BrowserObj()

    match browserType:
        case "chrome":
            browserObj.browserType = "chrome"

            temp = None
            for process in psutil.process_iter(["name", "exe"]):
                try:
                    # Check if the process name is 'chrome.exe'
                    if (
                        process.name().lower() == "chrome.exe"
                        and process.status() == psutil.STATUS_RUNNING
                    ):
                        # Return the executable path if found
                        temp = process.info["exe"]
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            if not temp:
                raise ChromeCommandError("Can't find a running 'chrome.exe' to bind.")
            else:
                browserObj.path = temp

            dictCommand = {"commandName": "get_chrome_socket_id"}
            strSocketId = send_command(
                eventName="application_command", command=dictCommand
            )
            if not strSocketId:
                raise ChromeCommandError(
                    "Can't access LiberRPA Chrome extension, if Chrome is running, you should install LiberRPA Chrome extension and turn it on."
                )
            else:
                browserObj.socketId = strSocketId

            return browserObj

        case _:
            raise ValueError(f"This is not a supported browser type: '{browserType}'")


@Log.trace()
@lock_ui_operation
def get_state(browserObj: BrowserObj) -> Literal["unloaded", "loading", "complete"]:
    """
    Get the active tab's state.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        str: one of "unloaded", "loading", "complete"
    """

    match browserObj.browserType:
        case "chrome":
            strState: Literal["unloaded", "loading", "complete"] = send_command(
                eventName="chrome_command", command={"commandName": "getState"}
            )

            return strState

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def go_backward(browserObj: BrowserObj) -> None:
    """
    Make the active tab go backward.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command", command={"commandName": "goBackward"}
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def go_forward(browserObj: BrowserObj) -> None:
    """
    Make the active tab go forward.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(eventName="chrome_command", command={"commandName": "goForward"})

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def refresh(browserObj: BrowserObj) -> None:
    """
    Make the active tab refresh.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(eventName="chrome_command", command={"commandName": "refresh"})

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def wait_load_completed(browserObj: BrowserObj, timeout: int = 30000) -> None:
    """
    Wait until the active browser tab finishes loading.

    Parameters:
        browserObj: The browser object to manipulate.
        timeout: Maximum time to wait for the active tab to finish loading, in milliseconds.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={"commandName": "waitForLoad", "timeout": timeout},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


def _check_url(url: str) -> None:
    urlParsed = urlparse(url)
    if not urlParsed.scheme:
        raise ValueError("URL must start with a protocol (e.g., http:// or https://)")


@Log.trace()
@lock_ui_operation
def navigate(
    browserObj: BrowserObj, url: str, waitForLoad: bool = False, timeout: int = 30000
) -> None:
    """
    Navigate the active tab to a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to navigate to. It should starts with a protocol, such as http:// or https://
        waitForLoad: If True, waits for the page load to complete before returning.
        timeout: The maximum time (in milliseconds) to wait for the page load to complete, applicable only if waitForLoad is True.
    """

    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "navigate",
                    "url": url,
                    "waitForLoad": waitForLoad,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def open_new_tab(
    browserObj: BrowserObj, url: str, waitForLoad: bool = False, timeout: int = 30000
) -> None:
    """
    Create a new tab to open a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to access. It should starts with a protocol, such as http:// or https://
        waitForLoad: If True, waits for the page load to complete before returning.
        timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitForLoad is True.
    """

    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "openNewTab",
                    "url": url,
                    "waitForLoad": waitForLoad,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def open_new_window(
    browserObj: BrowserObj, url: str, waitForLoad: bool = False, timeout: int = 30000
) -> None:
    """
    Create a new browser window to open a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to access. It should starts with a protocol, such as http:// or https://
        waitForLoad: If True, waits for the page load to complete before returning.
        timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitForLoad is True.
    """

    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "openNewWindow",
                    "url": url,
                    "waitForLoad": waitForLoad,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def switch_tab(browserObj: BrowserObj, titleOrIndex: str | int) -> None:
    """
    Switch to a specific tab of the active browser window.

    Parameters:
        browserObj: The browser object to manipulate.
        titleOrIndex: The target tab's title or index(start from 0)
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={"commandName": "switchTab", "titleOrIndex": titleOrIndex},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def close_current_tab(browserObj: BrowserObj) -> None:
    """
    Close the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={"commandName": "closeCurrentTab"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_download_list(
    browserObj: BrowserObj, limit: int = 5, timeout: int = 10000
) -> list[ChromeDownloadItem]:
    """
    Get recent download items from the browser.

    Parameters:
        browserObj: The browser object to manipulate.
        limit: Maximum number of download items to return.
        timeout: Maximum time to wait for the browser download query to complete, in milliseconds.

    Returns:
        list[ChromeDownloadItem]: A list of recent Chrome download items.
    """

    match browserObj.browserType:
        case "chrome":
            return _get_download_list(limit=limit, timeout=timeout)

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_source_code(browserObj: BrowserObj) -> str:
    """
    Get the HTML source code of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        str: The HTML source code of the active tab.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getSourceCode"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_all_text(browserObj: BrowserObj) -> str:
    """
    Get all text in the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        str: All text in the active tab.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getAllText"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_url(browserObj: BrowserObj) -> str:
    """
    Get the url of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        str: The URL of the active tab.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getUrl"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_title(browserObj: BrowserObj) -> str:
    """
    Get the title of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        str: The title of the active tab.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getTitle"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_cookies(browserObj: BrowserObj) -> list[DictCookiesOfChrome]:
    """
    Get the cookies of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        list[DictCookiesOfChrome]: The list of Chrome cookies standard attributes(refer to [Types-Cookie](https://developer.chrome.com/docs/extensions/reference/api/cookies#type-Cookie)), it will be improved with more browser type be added.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getCookies"},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def set_cookies(
    browserObj: BrowserObj,
    domain: str,
    name: str,
    path: str,
    value: str | None = None,
    expirationDate: int | None = None,
    httpOnly: bool | None = None,
    secure: bool | None = None,
    storeId: str | None = None,
    sameSite: Literal["no_restriction", "lax", "strict", "unspecified", None] = None,
) -> DictCookiesOfChrome:
    """
    Sets a cookie to the active tab with the given cookie data; may overwrite equivalent cookies if they exist.

    Parameters:
        browserObj: The browser object to manipulate.
        domain: The domain of the cookie.
        name: The name of the cookie.
        path: The path of the cookie.
        value: The value of the cookie. If it's None, it will use the original value in browser.
        expirationDate: The expiration date of the cookie as the number of seconds since the UNIX epoch. If it's None, it will use the original value in browser.
        httpOnly: Whether the cookie should be marked as HttpOnly. If it's None, it will use the original value in browser.
        secure: Whether the cookie should be marked as Secure. If it's None, it will use the original value in browser.
        storeId: The ID of the cookie store in which to set the cookie. If it's None, it will use the original value in browser.
        sameSite: The cookie's same-site status. If it's None, it will use the original value in browser.

    Returns:
        DictCookiesOfChrome: The updated Chrome cookies standard attributes(refer to [Types-Cookie](https://developer.chrome.com/docs/extensions/reference/api/cookies#type-Cookie)), it will be improved with more browser type be added.
    """

    # Combination of name, domain, and path: These three attributes typically form a unique identifier for each cookie. So set them to be required.

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={
                    "commandName": "setCookies",
                    "domain": domain,
                    "name": name,
                    "path": path,
                    "value": value,
                    "expirationDate": expirationDate,
                    "httpOnly": httpOnly,
                    "secure": secure,
                    "storeId": storeId,
                    "sameSite": sameSite,
                },
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def get_scroll_position(browserObj: BrowserObj) -> tuple[int, int]:
    """
    Get the scroll position of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.

    Returns:
        tuple[int,int]: The scrollX and scrollY.
    """

    match browserObj.browserType:
        case "chrome":
            temp: list[int] = send_command(
                eventName="chrome_command",
                command={"commandName": "getScrollPosition"},
            )

            if len(temp) != 2:
                raise ValueError(f"Expected 2 values, got {len(temp)}: {temp}")

            return (temp[0], temp[1])

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@Log.trace()
@lock_ui_operation
def set_scroll_position(browserObj: BrowserObj, x: int = 0, y: int = 0) -> None:
    """
    set the scroll position of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
        x: The pixel along the horizontal axis of the web page that you want displayed in the upper left.
        y: The pixel along the vertical axis of the web page that you want displayed in the upper left.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={"commandName": "setScrollPosition", "x": x, "y": y},
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


@overload
def execute_js_code(
    browserObj: BrowserObj,
    jsCode: str,
    returnImmediately: Literal[True],
) -> None: ...


@overload
def execute_js_code(
    browserObj: BrowserObj,
    jsCode: str,
    returnImmediately: Literal[False] = False,
) -> JsonValue: ...


@Log.trace()
@lock_ui_operation
def execute_js_code(
    browserObj: BrowserObj,
    jsCode: str,
    returnImmediately: bool = False,
) -> JsonValue | None:
    """
    Executes a JavaScript code string in the active tab of the specified browser.

    For Chrome, the code is executed by LiberRPA Chrome Extension's content script.
    This is not exactly the same as running code in the browser DevTools Console.

    Chrome content scripts normally run in an isolated environment. The executed code can access and manipulate the page DOM, such as `document`, `document.body`, and normal DOM nodes.
    However, it may not be able to access JavaScript variables, functions, or objects that
    exist only in the web page's own main-world JavaScript context.

    The current Chrome extension implementation catches JavaScript execution errors inside the content script and returns `null` instead of reporting the execution as a failed LiberRPA command. Therefore, a Python return value of `None` may mean one of the following:

    - `returnImmediately` is True.
    - The JavaScript code actually returned `null` or `undefined`.
    - The JavaScript code threw an error and the extension converted the error result to `null`.

    For reliable result passing, the JavaScript return value should be JSON-serializable.
    Recommended return values are strings, numbers, booleans, `null`, arrays, and plain objects.
    Avoid returning DOM nodes, functions, class instances, cyclic objects, Window objects,
    or other complex browser/runtime objects.

    Parameters:
        browserObj: The browser object to manipulate.
        jsCode: The JavaScript code to be executed.

            This can include expressions, function calls, or IIFE (Immediately Invoked Function Expressions).

            The code must be a valid JavaScript expression or function to execute correctly.
        returnImmediately: If True, the function will return None immediately after execution and will not wait for a result.

            If False, the function will wait for the JavaScript execution to complete and return the result of the JavaScript code.

    Returns:
        JsonValue | None: The returned value of the JavaScript code. It can be None, bool, int, float, str, list, or dict. Or None in the cases described above.

    Usage Example:
        ```python
        # Example 1: Execute a simple JavaScript expression and get the result
        result = execute_js_code(browserObj, jsCode="123 + 456", returnImmediately=False)
        print(result)  # Outputs: 579

        # Example 2: Execute an IIFE that returns a string
        result = execute_js_code(browserObj, jsCode="(function(){ return 'Hello, World!'; })()", returnImmediately=False)
        print(result)  # Outputs: 'Hello, World!'

        # Example 3: Execute JavaScript without waiting for the result
        execute_js_code(browserObj, jsCode="document.body.style.backgroundColor = 'blue';", returnImmediately=True)
        ```
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={
                    "commandName": "executeJsCode",
                    "jsCode": jsCode,
                    "returnImmediately": returnImmediately,
                },
            )

        case _:
            raise ValueError(
                f"Unsupported browser type in browserObj: {browserObj.browserType!r}. "
                "Currently only 'chrome' is supported."
            )


if __name__ == "__main__":
    browserObj = open_browser(browserType="chrome", path=None, params="")
    print(browserObj)
    # # import time

    # # time.sleep(3)
    # # print("Done.")

    # browserObj = bind_browser(browserType="chrome")
    # print(browserObj)

    # # refresh(browserObj=browserObj)
    # # print(get_state(browserObj=browserObj))
    # # wait_load_completed(browserObj=browserObj, timeout=3000)
    # # go_backward(browserObj=browserObj)
    # # go_forward(browserObj=browserObj)

    # # open_new_tab(browserObj=browserObj, url="https://www.reddit.com/", waitForLoad=True, timeout=2000)
    # # open_new_window(browserObj=browserObj, url="https://www.reddit.com/", waitForLoad=True, timeout=2000)
    # # switch_tab(browserObj=browserObj,titleOrIndex=1)
    # # close_current_tab(browserObj=browserObj)
    # # log.info(get_source_code(browserObj=browserObj))
    # # log.info(get_all_text(browserObj=browserObj))
    # # print(get_url(browserObj=browserObj))
    # # print(get_title(browserObj=browserObj))
    # # temp = get_cookies(browserObj=browserObj)
    # # print(temp)
    # # print(
    # #     set_cookies(
    # #         browserObj=browserObj, domain=temp[0]["domain"], name=temp[0]["name"], path=temp[0]["path"], value="123"
    # #     )
    # # )
    # # print(get_cookies(browserObj=browserObj))
    # # print(get_scroll_position(browserObj=browserObj))
    # # set_scroll_position(browserObj=browserObj,x=10,y=20)
    # # print(get_scroll_position(browserObj=browserObj))
    # print(
    #     execute_js_code(
    #         browserObj=browserObj, jsCode="""document.body.style.backgroundColor = 'blue';""", returnImmediately=False
    #     )
    # )
    # # print(
    # #     execute_js_code(
    # #         browserObj=browserObj, jsCode="""alert("Hello! I am an alert box!!");""", returnImmediately=False
    # #     )
    # # )
