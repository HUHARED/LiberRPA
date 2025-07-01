# FileName: SetSession.py
import os
import subprocess
import ctypes


def get_session_id() -> int:
    pid = os.getpid()
    sessionId = ctypes.c_ulong()
    if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(sessionId)) == 0:
        raise Exception("Failed to get session ID")
    print("Current session ID:", sessionId.value, flush=True)
    return sessionId.value


try:
    boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    print(f"Running as Admin: {boolIsAdmin}", flush=True)
    if not boolIsAdmin:
        raise Exception("Executor is not ran as administrator.")

    sessionId = get_session_id()
    consoleId = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
    print(f"Console ID: {consoleId}", flush=True)
    if sessionId == consoleId:
        print("Not need to run tscon command.", flush=True)
    else:
        subprocess.run(f"tscon {sessionId} /dest:console", shell=True, check=True)

except Exception as e:
    print(e, flush=True)
