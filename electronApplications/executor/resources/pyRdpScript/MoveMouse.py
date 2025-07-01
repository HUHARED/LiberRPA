# FileName: MoveMouse.py

import pyautogui
import time
import sys
import threading


def _listen_for_exit() -> None:
    for line in sys.stdin:
        if line.strip() == "Executor-terminated":
            print("MoveMouse process exits.", flush=True)

            # Use os._exit to force exit.
            import os

            os._exit(0)


listener_thread = threading.Thread(target=_listen_for_exit, daemon=True)
listener_thread.start()

if __name__ == "__main__":

    while True:
        try:
            intX, intY = pyautogui.position()
            # Every 30 seconds move mouse once.
            time.sleep(30)
            intXNew, intYNew = pyautogui.position()
            if intXNew == intX and intYNew == intY:
                # print("Move.", flush=True)
                pyautogui.moveTo(x=intX + 1, y=intY - 1, duration=0)
                pyautogui.moveTo(x=intX + 1, y=intY + 1, duration=0)
                pyautogui.moveTo(x=intX - 1, y=intY + 1, duration=0)
                pyautogui.moveTo(x=intX - 1, y=intY - 1, duration=0)
                pyautogui.moveTo(x=intX, y=intY, duration=0)
        except Exception as e:
            print(e, flush=True)
            time.sleep(30)
            continue
