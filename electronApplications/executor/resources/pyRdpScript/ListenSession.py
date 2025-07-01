# FileName: ListenSession.py

import win32gui
import win32con
import win32ts
import ctypes

# Constants for session change messages
WM_WTSSESSION_CHANGE = 0x02B1
# RDP
WTS_REMOTE_DISCONNECT = 0x4
# RDP
WTS_REMOTE_CONNECT = 0x3
# Session
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
# Console
WTS_CONSOLE_CONNECT = 0x1
WTS_CONSOLE_DISCONNECT = 0x2


# Window Procedure Callback: this function receives Windows messages.
def WndProc(hWnd, msg, wParam, lParam) -> int:
    if msg == WM_WTSSESSION_CHANGE:
        # wParam provides the session change event code.
        # print("Received WM_WTSSESSION_CHANGE, event code:", wParam)
        if wParam == WTS_REMOTE_DISCONNECT:
            print("Detected RDP disconnect event.", flush=True)
        elif wParam == WTS_REMOTE_CONNECT:
            print("Detected RDP connect event.", flush=True)
        elif wParam == WTS_SESSION_LOCK:
            print("Detected session lock event.", flush=True)
        elif wParam == WTS_SESSION_UNLOCK:
            print("Detected session unlock event.", flush=True)
        elif wParam == WTS_CONSOLE_DISCONNECT:
            print("Detected console disconnect event.", flush=True)
        elif wParam == WTS_CONSOLE_CONNECT:
            print("Detected console connect event.", flush=True)
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)


def register_session_notification() -> int:
    # Define a window class.
    hInstance = win32gui.GetModuleHandle(None)
    className = "HiddenSessionNotificationWindow"

    wc = win32gui.WNDCLASS()
    setattr(wc, "lpszClassName", "HiddenSessionNotificationWindow")
    setattr(wc, "hInstance", hInstance)
    setattr(wc, "lpfnWndProc", WndProc)

    atom = win32gui.RegisterClass(wc)

    # Create a hidden window (message-only window)
    # Using HWND_MESSAGE as parent creates a message-only window.
    hWnd = win32gui.CreateWindow(atom, className, 0, 0, 0, 0, 0, win32con.HWND_MESSAGE, 0, hInstance, None)
    if not hWnd:
        raise Exception("Failed to create hidden window")

    # Register for session notifications.
    wtsapi32 = ctypes.windll.wtsapi32
    if not wtsapi32.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_ALL_SESSIONS):
        raise Exception("Failed to register for session notifications")

    print("Session notifications registered. hWnd =", hWnd, flush=True)
    return hWnd


if __name__ == "__main__":
    # Register the hidden window and run the message pump.
    hWnd = register_session_notification()
    print("Starting message pump. Waiting for session change events...", flush=True)
    win32gui.PumpMessages()
