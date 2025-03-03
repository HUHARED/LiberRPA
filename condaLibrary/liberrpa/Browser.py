# FileName: Browser.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command
from liberrpa.Common._Exception import ChromeError
from liberrpa.Common._TypedValue import DictCookiesOfChrome, ChromeDownloadItem
from liberrpa.Common._Chrome import get_download_list as _get_download_list

from pathlib import Path
import time
import psutil
from urllib.parse import urlparse
from typing import Literal, Any

CHROMEPATHX86 = R"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
CHROMEPATHX64 = R"C:/Program Files/Google/Chrome/Application/chrome.exe"


class BrowserObj:
    def __init__(self) -> None:
        self.browserType: Literal["chrome"]
        self.path: str
        self.socketId: str

    def __str__(self) -> str:
        return f"BrowserObj(type: {self.browserType}, path: {self.path}, socketId: {self.socketId})"


@Log.trace()
def open_browser(
    browserType: Literal["chrome"] = "chrome",
    url: str = "about:blank",
    path: str | None = None,
    params: str = "",
    timeout: int = 30000,
) -> BrowserObj:
    """
    Open a browser to access the url.

    If the browser is running, it will open a new tab.

    Parameters:
        browserType: The type of browser to manipulate (currently only "chrome" is supported).
        url: The URL to open in the browser.
        path: The filesystem path to the browser exe. If not provided, it attempts to locate the browser in common directories.
        params: Additional command-line parameters to pass when launching browser.

            Such as "--start-maximized".

            For Chrome, you can check all params in [List of Chromium Command Line Switches](https://peter.sh/experiments/chromium-command-line-switches/)

    Returns:
        BrowserObj: An object representing the browser session.
    """

    browserObj = BrowserObj()

    match browserType:
        case "chrome":
            browserObj.browserType = "chrome"

            if not path:
                if Path(CHROMEPATHX64).is_file():
                    browserObj.path = CHROMEPATHX64
                elif Path(CHROMEPATHX86).is_file():
                    browserObj.path = CHROMEPATHX86
                else:
                    raise FileNotFoundError(
                        f"Could not find Chrome executable at '{CHROMEPATHX64}' or '{CHROMEPATHX86}'."
                    )
            else:
                if Path(path).is_file():
                    browserObj.path = path
                else:
                    raise FileNotFoundError(f"Not find a file at '{path}'.")

            dictCommand = {"commandName": "open_browser", "url": url, "path": browserObj.path, "params": params}
            send_command(eventName="application_command", command=dictCommand)

            # Make sure Chrome extension is working.
            dictCommand = {"commandName": "get_chrome_socket_id"}
            timeStart = time.time()
            while True:
                strSocketId = send_command(eventName="application_command", command=dictCommand)
                if not strSocketId:
                    if (time.time() - timeStart) * 1000 <= timeout:
                        continue
                    else:
                        raise ChromeError(
                            f"Can't access LiberRPA Chrome extension after {timeout} milliseconds, if Chrome is running, you should install LiberRPA Chrome extension and turn it on."
                        )
                else:
                    browserObj.socketId = strSocketId
                    break
            return browserObj

        case _:
            raise ValueError(f"This not a supported browser type: '{browserType}'")


@Log.trace()
def bind_browser(browserType: Literal["chrome"] = "chrome") -> BrowserObj:
    """
    Bind a running browser.

    Parameters:
        browserType: The type of browser to manipulate (currently only "chrome" is supported).

    Returns:
        BrowserObj: An object representing the browser session.
    """
    browserObj = BrowserObj()

    match browserType:
        case "chrome":
            browserObj.browserType = "chrome"

            temp = None
            for process in psutil.process_iter(["name", "exe"]):
                try:
                    # Check if the process name is 'chrome.exe'
                    if process.name().lower() == "chrome.exe" and process.status() == "running":
                        # Return the executable path if found
                        temp = process.info["exe"]
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            if not temp:
                raise ChromeError(f"Can't find a running 'chrome.exe' to bind.")
            else:
                browserObj.path = temp

            dictCommand = {"commandName": "get_chrome_socket_id"}
            strSocketId = send_command(eventName="application_command", command=dictCommand)
            if not strSocketId:
                raise ChromeError(
                    f"Can't access LiberRPA Chrome extension, if Chrome is running, you should install LiberRPA Chrome extension and turn it on."
                )
            else:
                browserObj.socketId = strSocketId

            return browserObj

        case _:
            raise ValueError(f"This not a supported browser type: '{browserType}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def go_backward(browserObj: BrowserObj) -> None:
    """
    Make the active tab go backward.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(eventName="chrome_command", command={"commandName": "goBackward"})

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def wait_load_completed(browserObj: BrowserObj, timeout: int = 30000) -> None:
    """
    Wait for the active tab being loaded completed.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            send_command(eventName="chrome_command", command={"commandName": "waitLoadCompleted", "timeout": timeout})

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


def _check_url(url: str) -> None:
    urlParsed = urlparse(url)
    if not urlParsed.scheme:
        raise ValueError("URL must start with a protocol (e.g., http:// or https://)")


@Log.trace()
def navigate(browserObj: BrowserObj, url: str, waitLoadCompleted: bool = False, timeout: int = 30000) -> None:
    """
    Navigate the active tab to a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to navigate to. It should starts with a protocol, such as http:// or https://
        waitLoadCompleted: If True, waits for the page load to complete before returning.
        timeout: The maximum time (in milliseconds) to wait for the page load to complete, applicable only if waitLoadCompleted is True.
    """

    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "navigate",
                    "url": url,
                    "waitLoadCompleted": waitLoadCompleted,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def open_new_tab(browserObj: BrowserObj, url: str, waitLoadCompleted: bool = False, timeout: int = 30000) -> None:
    """
    Create a new tab to open a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to access. It should starts with a protocol, such as http:// or https://
        waitLoadCompleted: If True, waits for the page load to complete before returning.
        timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitLoadCompleted is True.
    """

    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "openNewTab",
                    "url": url,
                    "waitLoadCompleted": waitLoadCompleted,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def open_new_window(browserObj: BrowserObj, url: str, waitLoadCompleted: bool = False, timeout: int = 30000) -> None:
    """
    Create a new browser window to open a specified url.
    The url should starts with a protocol, such as http:// or https://

    Parameters:
        browserObj: The browser object to manipulate.
        url: The URL to access. It should starts with a protocol, such as http:// or https://
        waitLoadCompleted: If True, waits for the page load to complete before returning.
        timeout: The maximum time in milliseconds to wait for the page load to complete, applicable only if waitLoadCompleted is True.
    """
    
    _check_url(url=url)

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={
                    "commandName": "openNewWindow",
                    "url": url,
                    "waitLoadCompleted": waitLoadCompleted,
                    "timeout": timeout,
                },
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def switch_tab(browserObj: BrowserObj, titleOrIndex: str | int) -> None:
    """
    Switch to a specific tab of the active browser window.

    Parameters:
        browserObj: The browser object to manipulate.
        titleOrIndex: The target tab's tile or index(start from 0)
    """

    match browserObj.browserType:
        case "chrome":
            send_command(
                eventName="chrome_command",
                command={"commandName": "switchTab", "titleOrIndex": titleOrIndex},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def get_download_list(browserObj: BrowserObj, limit: int = 5, timeout: int = 10000) -> list[ChromeDownloadItem]:

    match browserObj.browserType:
        case "chrome":
            return _get_download_list(limit=limit, timeout=timeout)

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def get_source_code(browserObj: BrowserObj) -> str:
    """
    Get the HTML source code of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getSourceCode"},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def get_all_text(browserObj: BrowserObj) -> str:
    """
    Get all text in the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getAllText"},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def get_url(browserObj: BrowserObj) -> str:
    """
    Get the url of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getUrl"},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def get_title(browserObj: BrowserObj) -> str:
    """
    Get the title of the active tab.

    Parameters:
        browserObj: The browser object to manipulate.
    """

    match browserObj.browserType:
        case "chrome":
            return send_command(
                eventName="chrome_command",
                command={"commandName": "getTitle"},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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

            return tuple(temp)  # type: ignore - it has 2 item.

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
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
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


@Log.trace()
def execute_js_code(browserObj: BrowserObj, jsCode: str, returnImmediately: bool = False) -> Any:
    """
    Executes a JavaScript code string in the active tab of the specified browser.

    This function allows you to run JavaScript code in the context of the current active tab's web page.

    The code is executed as if it were being run directly in the browser's developer console.

    Parameters:
        browserObj: The browser object to manipulate.
        jsCode: The JavaScript code to be executed.

            This can include expressions, function calls, or IIFE (Immediately Invoked Function Expressions).

            The code must be a valid JavaScript expression or function to execute correctly.
        returnImmediately: If True, the function will return None immediately after execution and will not wait for a result.

            If False, the function will wait for the JavaScript execution to complete and return the result of the JavaScript code.

    Returns:
        the returned value of JavaScript code. It will alway be None if returnImmediately is True.

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
                command={"commandName": "executeJsCode", "jsCode": jsCode, "returnImmediately": returnImmediately},
            )

        case _:
            raise ValueError(f"(!!!It should not appear.)Not support the browser: '{browserObj}'")


if __name__ == "__main__":
    # browserObj = open_browser(browserType="chrome", path=None, params="")
    # print(browserObj)
    # import time

    # time.sleep(3)
    # print("Done.")

    browserObj = bind_browser(browserType="chrome")
    print(browserObj)

    # refresh(browserObj=browserObj)
    # print(get_state(browserObj=browserObj))
    # wait_load_completed(browserObj=browserObj, timeout=3000)
    # go_backward(browserObj=browserObj)
    # go_forward(browserObj=browserObj)

    # open_new_tab(browserObj=browserObj, url="https://www.reddit.com/", waitLoadCompleted=True, timeout=2000)
    # open_new_window(browserObj=browserObj, url="https://www.reddit.com/", waitLoadCompleted=True, timeout=2000)
    # switch_tab(browserObj=browserObj,titleOrIndex=1)
    # close_current_tab(browserObj=browserObj)
    # log.info(get_source_code(browserObj=browserObj))
    # log.info(get_all_text(browserObj=browserObj))
    # print(get_url(browserObj=browserObj))
    # print(get_title(browserObj=browserObj))
    # temp = get_cookies(browserObj=browserObj)
    # print(temp)
    # print(
    #     set_cookies(
    #         browserObj=browserObj, domain=temp[0]["domain"], name=temp[0]["name"], path=temp[0]["path"], value="123"
    #     )
    # )
    # print(get_cookies(browserObj=browserObj))
    # print(get_scroll_position(browserObj=browserObj))
    # set_scroll_position(browserObj=browserObj,x=10,y=20)
    # print(get_scroll_position(browserObj=browserObj))
    print(
        execute_js_code(
            browserObj=browserObj, jsCode="""document.body.style.backgroundColor = 'blue';""", returnImmediately=False
        )
    )
    # print(
    #     execute_js_code(
    #         browserObj=browserObj, jsCode="""alert("Hello! I am an alert box!!");""", returnImmediately=False
    #     )
    # )
