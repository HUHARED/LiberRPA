# FileName: MoveMouse.py

import ctypes
import sys
import threading
import pyautogui

pyautogui.FAILSAFE = False


_TERMINATION_MESSAGE = "Executor-stop-move-mouse"
_INT_MOVE_INTERVAL_SECOND = 30
_INT_SM_XVIRTUALSCREEN = 76
_INT_SM_YVIRTUALSCREEN = 77
_INT_SM_CXVIRTUALSCREEN = 78
_INT_SM_CYVIRTUALSCREEN = 79
_eventExit = threading.Event()


def _listen_for_exit() -> None:
    for strLine in sys.stdin:
        if strLine.strip() == _TERMINATION_MESSAGE:
            print("MoveMouse process exits.", flush=True)

            break

    _eventExit.set()


def _get_virtual_screen_bounds() -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    intLeft = user32.GetSystemMetrics(_INT_SM_XVIRTUALSCREEN)
    intTop = user32.GetSystemMetrics(_INT_SM_YVIRTUALSCREEN)
    intWidth = user32.GetSystemMetrics(_INT_SM_CXVIRTUALSCREEN)
    intHeight = user32.GetSystemMetrics(_INT_SM_CYVIRTUALSCREEN)
    if intWidth <= 0 or intHeight <= 0:
        raise RuntimeError("Failed to get the virtual screen bounds.")

    return intLeft, intTop, intLeft + intWidth - 1, intTop + intHeight - 1


def _move_mouse_once(intX: int, intY: int) -> None:
    intLeft, intTop, intRight, intBottom = _get_virtual_screen_bounds()
    if not (intLeft <= intX <= intRight and intTop <= intY <= intBottom):
        raise RuntimeError(
            f"Mouse position is outside the virtual screen: {intX}, {intY}"
        )

    if intX < intRight:
        tupleTarget = (intX + 1, intY)
    elif intX > intLeft:
        tupleTarget = (intX - 1, intY)
    elif intY < intBottom:
        tupleTarget = (intX, intY + 1)
    elif intY > intTop:
        tupleTarget = (intX, intY - 1)
    else:
        return

    pyautogui.moveTo(*tupleTarget, duration=0)
    pyautogui.moveTo(intX, intY, duration=0)


def main() -> None:
    threadListener = threading.Thread(target=_listen_for_exit, daemon=True)
    threadListener.start()

    while not _eventExit.is_set():
        try:
            intX, intY = pyautogui.position()
            if _eventExit.wait(_INT_MOVE_INTERVAL_SECOND):
                break

            intXNew, intYNew = pyautogui.position()
            if intXNew == intX and intYNew == intY:
                _move_mouse_once(intX, intY)
        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            if _eventExit.wait(_INT_MOVE_INTERVAL_SECOND):
                break


if __name__ == "__main__":
    main()
