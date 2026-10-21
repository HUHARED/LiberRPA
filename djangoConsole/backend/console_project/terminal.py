# FileName: terminal.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
import sys
from getpass import GetPassWarning, getpass
import warnings

_INT_ENABLE_PROCESSED_INPUT = 0x0001
_INT_ENABLE_LINE_INPUT = 0x0002
_INT_ENABLE_ECHO_INPUT = 0x0004
_INT_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200


class PasswordInputError(RuntimeError):
    """Hidden password input could not be completed safely."""


def read_password(prompt: str) -> str:
    """Read a hidden password while preserving the terminal's line editing."""
    if os.name != "nt":
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            try:
                return getpass(prompt)
            except GetPassWarning:
                raise PasswordInputError(
                    "Use an interactive terminal to enter the password without echo."
                ) from None

    if not sys.stdin.isatty():
        raise PasswordInputError(
            "Use an interactive terminal to enter the password without echo."
        )

    import ctypes
    from ctypes import wintypes
    import msvcrt

    consoleApi = ctypes.WinDLL("kernel32", use_last_error=True)
    getConsoleMode = consoleApi.GetConsoleMode
    getConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    getConsoleMode.restype = wintypes.BOOL
    setConsoleMode = consoleApi.SetConsoleMode
    setConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    setConsoleMode.restype = wintypes.BOOL

    consoleHandle = msvcrt.get_osfhandle(sys.stdin.fileno())
    originalMode = wintypes.DWORD()
    if not getConsoleMode(consoleHandle, ctypes.byref(originalMode)):
        raise PasswordInputError(
            f"Cannot read console input settings (Windows error {ctypes.get_last_error()})."
        )

    # Keep native paste and line editing; getwch() switches to raw keyboard input.
    intPasswordMode = (
        originalMode.value | _INT_ENABLE_PROCESSED_INPUT | _INT_ENABLE_LINE_INPUT
    ) & ~(_INT_ENABLE_ECHO_INPUT | _INT_ENABLE_VIRTUAL_TERMINAL_INPUT)
    if not setConsoleMode(consoleHandle, intPasswordMode):
        raise PasswordInputError(
            f"Cannot hide password input (Windows error {ctypes.get_last_error()})."
        )

    try:
        sys.stderr.write(prompt)
        sys.stderr.flush()
        strPassword = sys.stdin.readline()
    finally:
        if not setConsoleMode(consoleHandle, originalMode.value):
            raise PasswordInputError(
                f"Cannot restore console input settings (Windows error {ctypes.get_last_error()})."
            )
        sys.stderr.write("\n")
        sys.stderr.flush()

    if not strPassword:
        raise EOFError
    return strPassword.removesuffix("\n").removesuffix("\r")
