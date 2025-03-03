# FileName: _TypedValue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.UI._UiDict import *
from typing import TypedDict, Literal, NotRequired, Any


type Encoding = Literal[
    None,
    "ascii",
    "big5",
    "big5hkscs",
    "cp037",
    "cp273",
    "cp424",
    "cp437",
    "cp500",
    "cp720",
    "cp737",
    "cp775",
    "cp850",
    "cp852",
    "cp855",
    "cp856",
    "cp857",
    "cp858",
    "cp860",
    "cp861",
    "cp862",
    "cp863",
    "cp864",
    "cp865",
    "cp866",
    "cp869",
    "cp874",
    "cp875",
    "cp932",
    "cp949",
    "cp950",
    "cp1006",
    "cp1026",
    "cp1125",
    "cp1140",
    "cp1250",
    "cp1251",
    "cp1252",
    "cp1253",
    "cp1254",
    "cp1255",
    "cp1256",
    "cp1257",
    "cp1258",
    "euc_jp",
    "euc_jis_2004",
    "euc_jisx0213",
    "euc_kr",
    "gb2312",
    "gbk",
    "gb18030",
    "hz",
    "iso2022_jp",
    "iso2022_jp_1",
    "iso2022_jp_2",
    "iso2022_jp_2004",
    "iso2022_jp_3",
    "iso2022_jp_ext",
    "iso2022_kr",
    "latin_1",
    "iso8859_2",
    "iso8859_3",
    "iso8859_4",
    "iso8859_5",
    "iso8859_6",
    "iso8859_7",
    "iso8859_8",
    "iso8859_9",
    "iso8859_10",
    "iso8859_11",
    "iso8859_13",
    "iso8859_14",
    "iso8859_15",
    "iso8859_16",
    "johab",
    "koi8_r",
    "koi8_t",
    "koi8_u",
    "kz1048",
    "mac_cyrillic",
    "mac_greek",
    "mac_iceland",
    "mac_latin2",
    "mac_roman",
    "mac_turkish",
    "ptcp154",
    "shift_jis",
    "shift_jis_2004",
    "shift_jisx0213",
    "utf_32",
    "utf_32_be",
    "utf_32_le",
    "utf_16",
    "utf_16_be",
    "utf_16_le",
    "utf_7",
    "utf_8",
    "utf-8",
    "utf_8_sig",
]


# Mail
class DictImapMailInfo(TypedDict):
    subject: str
    from_: list[tuple[str, str]]
    to: list[tuple[str, str]]
    cc: list[tuple[str, str]] | None
    bcc: list[tuple[str, str]] | None
    date: str
    received: list[dict[str, Any]]
    text_plain: list[str]
    text_html: list[str]
    attachments: list[dict[str, Any]]
    headers: dict[str, str]
    message_id: str
    to_domains: str | list[str]
    from_domains: str | list[str] | None
    cc_domains: str | list[str] | None
    bcc_domains: str | list[str] | None
    delivered_to: list[str] | None
    reply_to: list[str] | None
    body: str
    anomalies: str | None
    mail: dict[str, Any]
    defects: list[Any] | None
    defects_category: str | None
    has_defects: bool | None


class DictOutlookMailInfo(TypedDict):
    Subject: str
    Body: str
    HTMLBody: str
    SenderEmailAddress: str
    SenderName: str
    To: str
    CC: str
    BCC: str
    ReceivedTime: str
    SentOn: str
    Importance: Literal["high", "normal", "low"]
    Attachments: str
    Size: int
    # NOTE: More properties can get, check them by dir(the CDispatch object)


# SocketIO
class DictSocketResult(TypedDict):
    boolSuccess: bool
    data: Any


# Chrome
type ChromeDownloadItemDanger = Literal[
    "file",
    "url",
    "content",
    "uncommon",
    "host",
    "unwanted",
    "safe",
    "accepted",
    "allowlistedByPolicy",
    "asyncScanning",
    "asyncLocalPasswordScanning",
    "passwordProtected",
    "blockedTooLarge",
    "sensitiveContentWarning",
    "sensitiveContentBlock",
    "deepScannedFailed",
    "deepScannedSafe",
    "deepScannedOpenedDangerous",
    "promptForScanning",
    "promptForLocalPasswordScanning",
    "accountCompromise",
    "blockedScanFailed",
]
type ChromeDownloadItemInterruptReason = Literal[
    "FILE_FAILED",
    "FILE_ACCESS_DENIED",
    "FILE_NO_SPACE",
    "FILE_NAME_TOO_LONG",
    "FILE_TOO_LARGE",
    "FILE_VIRUS_INFECTED",
    "FILE_TRANSIENT_ERROR",
    "FILE_BLOCKED",
    "FILE_SECURITY_CHECK_FAILED",
    "FILE_TOO_SHORT",
    "FILE_HASH_MISMATCH",
    "FILE_SAME_AS_SOURCE",
    "NETWORK_FAILED",
    "NETWORK_TIMEOUT",
    "NETWORK_DISCONNECTED",
    "NETWORK_SERVER_DOWN",
    "NETWORK_INVALID_REQUEST",
    "SERVER_FAILED",
    "SERVER_NO_RANGE",
    "SERVER_BAD_CONTENT",
    "SERVER_UNAUTHORIZED",
    "SERVER_CERT_PROBLEM",
    "SERVER_FORBIDDEN",
    "SERVER_UNREACHABLE",
    "SERVER_CONTENT_LENGTH_MISMATCH",
    "SERVER_CROSS_ORIGIN_REDIRECT",
    "USER_CANCELED",
    "USER_SHUTDOWN",
    "CRASH",
]
type ChromeDownloadItemState = Literal["in_progress", "interrupted", "complete"]


class ChromeDownloadItem(TypedDict):
    byExtensionId: NotRequired[str]
    byExtensionName: NotRequired[str]
    bytesReceived: int
    canResume: bool
    danger: ChromeDownloadItemDanger
    endTime: NotRequired[str]
    error: NotRequired[ChromeDownloadItemInterruptReason]
    estimatedEndTime: NotRequired[str]
    exists: bool
    fileSize: int
    filename: str
    finalUrl: str
    id: int
    incognito: bool
    mime: str
    paused: bool
    referrer: str
    startTime: str
    state: ChromeDownloadItemState
    totalBytes: int
    url: str


class DictCookiesOfChrome(TypedDict):
    # Base on https://developer.chrome.com/docs/extensions/reference/api/cookies#type-Cookie
    domain: str
    name: str
    path: str
    value: str
    expirationDate: NotRequired[int]
    hostOnly: bool
    httpOnly: bool
    secure: bool
    session: bool
    storeId: NotRequired[str]
    sameSite: Literal["no_restriction", "lax", "strict", "unspecified"]


# OCR
class DictTextBlock(TypedDict):
    text: str
    top_left_x: int
    top_left_y: int
    top_right_x: int
    top_right_y: int
    bottom_left_x: int
    bottom_left_y: int
    bottom_right_x: int
    bottom_right_y: int


# UI Automation
# The key name of pyautogui
# NOTE: Do not use type, otherwise can get its __args__, I don't know why.
InputKey = Literal[
    # Standard keys
    "enter",
    "esc",
    "tab",
    "space",
    "backspace",
    "up",
    "down",
    "left",
    "right",
    "delete",
    "insert",
    "home",
    "end",
    "pageup",
    "pagedown",
    "capslock",
    "numlock",
    "printscreen",
    "scrolllock",
    "pause",
    # Letters
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    # Numbers
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    # Numeric keypad numbers
    "num0",
    "num1",
    "num2",
    "num3",
    "num4",
    "num5",
    "num6",
    "num7",
    "num8",
    "num9",
    # Numeric keypad keys
    "add",
    "subtract",
    "multiply",
    "divide",
    "decimal",
    # "separator",
    # Function keys
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "f13",
    "f14",
    "f15",
    "f16",
    "f17",
    "f18",
    "f19",
    "f20",
    "f21",
    "f22",
    "f23",
    "f24",
    # Special characters
    # Line 1
    "`",
    "~",
    "!",
    "@",
    "#",
    "$",
    "%",
    "^",
    "&",
    "*",
    "(",
    ")",
    "-",
    "_",
    "=",
    "+",
    # Line 2
    "[",
    "{",
    "]",
    "}",
    "\\",
    "|",
    # Line 3
    ";",
    ":",
    "'",
    '"',
    # Line 4
    ",",
    "<",
    ".",
    ">",
    "/",
    "?",
    # Modifiers
    "shift",
    "shiftleft",
    "shiftright",
    "ctrl",
    "ctrlleft",
    "ctrlright",
    "alt",
    "altleft",
    "altright",
    "win",
    "winleft",
    "winright",
    # Multimedia keys
    "volumemute",
    "volumedown",
    "volumeup",
    "playpause",
    "stop",
    "nexttrack",
    "prevtrack",
    # Browser control
    "browserback",
    "browserfavorites",
    "browserforward",
    "browserhome",
    "browserrefresh",
    "browsersearch",
    "browserstop",
]


HookKey = Literal[
    # Modifiers
    "ctrl",
    "left ctrl",
    "right ctrl",
    "shift",
    "left shift",
    "right shift",
    "alt",
    "left alt",
    "right alt",
    "windows",
    "left windows",
    "right windows",
    #
    "tab",
    "space",
    "enter",
    "esc",
    #
    "caps lock",
    #
    "left menu",
    "right menu",
    #
    "backspace",
    "insert",
    "delete",
    "end",
    "home",
    "page up",
    "page down",
    # Direction
    "left",
    "up",
    "right",
    "down",
    #
    "print screen",
    "scroll lock",
    "pause",
    "num lock",
    # number
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    # English characters
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    # Special characters
    # Line 1
    "`",
    "~",
    "!",
    "@",
    "#",
    "$",
    "%",
    "^",
    "&",
    "*",
    "(",
    ")",
    "-",
    "_",
    "=",
    "+",
    # Line 2
    "[",
    "{",
    "]",
    "}",
    "\\",
    "|",
    # Line 3
    ";",
    ":",
    "'",
    '"',
    # Line 4
    ",",
    "<",
    ".",
    ">",
    "/",
    "?",
    # Numeric keypad keys
    "separator",
    "decimal",
    # Function keys
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "f13",
    "f14",
    "f15",
    "f16",
    "f17",
    "f18",
    "f19",
    "f20",
    "f21",
    "f22",
    "f23",
    "f24",
    # Multimedia keys
    "browser back",
    "browser forward",
    "browser refresh",
    "browser stop",
    "browser search key",
    "browser favorites",
    "browser start and home",
    "volume mute",
    "volume down",
    "volume up",
    "next track",
    "previous track",
    "stop media",
    "play/pause media",
    "start mail",
    "select media",
    "start application 1",
    "start application 2",
    # Other
    "spacebar",
    "clear",
    "select",
    "print",
    "execute",
    "help",
    "control-break processing",
    "applications",
    "sleep",
]

type MouseButton = Literal["left", "right", "middle"]
type ClickMode = Literal["single_click", "double_click", "down", "up"]
type FivePosition = Literal["center", "top_left", "top_right", "bottom_left", "bottom_right"]
type ExecutionMode = Literal["simulate", "api"]


if __name__ == "__main__":
    print(DictTextBlock.__annotations__)
