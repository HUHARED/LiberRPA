# FileName: ListenSession.py

import ctypes
import sys
import threading
from ctypes import wintypes
import win32con
import win32gui
import win32ts


_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_CONSOLE_CONNECT = 0x1
_WTS_CONSOLE_DISCONNECT = 0x2
_WTS_REMOTE_CONNECT = 0x3
_WTS_REMOTE_DISCONNECT = 0x4
_WTS_SESSION_LOCK = 0x7
_WTS_SESSION_UNLOCK = 0x8
_TERMINATION_MESSAGE = "Executor-stop-listen-session"

_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
_wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
_wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL
_wtsapi32.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
_wtsapi32.WTSUnRegisterSessionNotification.restype = wintypes.BOOL


def _unregister_session_notification(hWnd: int) -> None:
    if _wtsapi32.WTSUnRegisterSessionNotification(hWnd) == 0:
        intErrorCode = ctypes.get_last_error()
        print(
            f"Failed to unregister session notifications: error code {intErrorCode}",
            file=sys.stderr,
            flush=True,
        )


def _window_proc(hWnd: int, intMessage: int, intEvent: int, intSessionId: int) -> int:
    if intMessage == _WM_WTSSESSION_CHANGE:
        if intEvent == _WTS_REMOTE_DISCONNECT:
            print("Detected RDP disconnect event.", flush=True)
        elif intEvent == _WTS_REMOTE_CONNECT:
            print("Detected RDP connect event.", flush=True)
        elif intEvent == _WTS_SESSION_LOCK:
            print("Detected session lock event.", flush=True)
        elif intEvent == _WTS_SESSION_UNLOCK:
            print("Detected session unlock event.", flush=True)
        elif intEvent == _WTS_CONSOLE_DISCONNECT:
            print("Detected console disconnect event.", flush=True)
        elif intEvent == _WTS_CONSOLE_CONNECT:
            print("Detected console connect event.", flush=True)
    elif intMessage == win32con.WM_CLOSE:
        _unregister_session_notification(hWnd)
        win32gui.DestroyWindow(hWnd)
        return 0
    elif intMessage == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0

    return win32gui.DefWindowProc(hWnd, intMessage, intEvent, intSessionId)


def _register_session_notification() -> int:
    hInstance = win32gui.GetModuleHandle(None)
    strClassName = "LiberRPAExecutorSessionNotificationWindow"

    windowClass = win32gui.WNDCLASS()
    windowClass.lpszClassName = strClassName
    windowClass.hInstance = hInstance
    windowClass.lpfnWndProc = _window_proc

    intAtom = win32gui.RegisterClass(windowClass)
    hWnd = win32gui.CreateWindow(
        intAtom,
        strClassName,
        0,
        0,
        0,
        0,
        0,
        win32con.HWND_MESSAGE,
        0,
        hInstance,
        None,
    )
    if not hWnd:
        raise RuntimeError("Failed to create the hidden Session notification window.")

    if (
        _wtsapi32.WTSRegisterSessionNotification(
            hWnd,
            win32ts.NOTIFY_FOR_THIS_SESSION,
        )
        == 0
    ):
        intErrorCode = ctypes.get_last_error()
        win32gui.DestroyWindow(hWnd)
        raise RuntimeError(
            f"Failed to register Session notifications: error code {intErrorCode}"
        )

    print(f"Session notifications registered. hWnd={hWnd}", flush=True)
    return hWnd


def _listen_for_exit(hWnd: int) -> None:
    for strLine in sys.stdin:
        if strLine.strip() == _TERMINATION_MESSAGE:
            break

    if win32gui.IsWindow(hWnd):
        win32gui.PostMessage(hWnd, win32con.WM_CLOSE, 0, 0)


def main() -> None:
    hWnd = _register_session_notification()
    threadListener = threading.Thread(
        target=_listen_for_exit,
        args=(hWnd,),
        daemon=True,
    )
    threadListener.start()

    print("Starting message pump. Waiting for Session change events.", flush=True)
    try:
        win32gui.PumpMessages()
    finally:
        if win32gui.IsWindow(hWnd):
            _unregister_session_notification(hWnd)
            win32gui.DestroyWindow(hWnd)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr, flush=True)
        sys.exit(1)
