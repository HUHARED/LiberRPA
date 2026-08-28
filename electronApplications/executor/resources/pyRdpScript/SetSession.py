# FileName: SetSession.py

import ctypes
import os
import subprocess
import sys


def get_session_id() -> int:
    pid = os.getpid()
    sessionId = ctypes.c_ulong()
    if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(sessionId)) == 0:
        raise RuntimeError("Failed to get session ID.")
    print("Current session ID:", sessionId.value, flush=True)
    return sessionId.value


def main() -> None:
    boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    print(f"Running as Admin: {boolIsAdmin}", flush=True)
    if not boolIsAdmin:
        raise RuntimeError("Executor is not running as administrator.")

    sessionId = get_session_id()
    consoleId = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
    print(f"Console ID: {consoleId}", flush=True)
    if sessionId == consoleId:
        print("No need to run tscon command.", flush=True)
        return

    subprocess.run(
        ["tscon", str(sessionId), "/dest:console"],
        check=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr, flush=True)
        sys.exit(1)
