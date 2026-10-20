# FileName: process_events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
import sys
import time
from collections import defaultdict, deque
from typing import cast
from xmlrpc.client import Fault

from supervisor import childutils
from supervisor.xmlrpc import Faults

_SET_CORE_PROCESS = {"postgres", "proxy", "static", "web", "job-worker", "scheduler"}
_INT_RESTART_WINDOW_SECONDS = 300
_INT_MAX_RESTARTS = 3


def main() -> None:
    rpc = childutils.getRPCInterface(os.environ).supervisor
    dictExit: dict[str, deque[float]] = defaultdict(deque)
    while True:
        headers, payload = childutils.listener.wait(sys.stdin, sys.stdout)
        dictEvent = dict(part.split(":", 1) for part in payload.split())
        strName = dictEvent["processname"]
        strEvent = headers["eventname"]
        # Supervisor also delivers events from this listener's previous process.
        childutils.listener.ok(sys.stdout)
        if strName == "process-events":
            continue
        floatNow = time.monotonic()
        exits = dictExit[strName]
        while exits and exits[0] <= floatNow - _INT_RESTART_WINDOW_SECONDS:
            exits.popleft()
        boolExhausted = (
            strEvent == "PROCESS_STATE_FATAL" or len(exits) >= _INT_MAX_RESTARTS
        )
        dictState = cast(dict[str, object], rpc.getState())
        if dictState["statename"] != "RUNNING":
            continue
        if boolExhausted:
            print(f"{strName}: recovery attempts exhausted.", file=sys.stderr, flush=True)
            if strName in _SET_CORE_PROCESS:
                rpc.shutdown()
                return
            # Auxiliary failure remains visible without restarting unrelated core services.
            continue
        exits.append(floatNow)
        print(
            f"{strName}: restarting after exit ({len(exits)}/{_INT_MAX_RESTARTS}).",
            file=sys.stderr,
            flush=True,
        )
        try:
            rpc.startProcess(strName, False)
        except Fault as e:
            if e.faultCode == Faults.ALREADY_STARTED:
                continue
            print(
                f"{strName}: Supervisor could not restart the process (code {e.faultCode}).",
                file=sys.stderr,
                flush=True,
            )
            if strName in _SET_CORE_PROCESS:
                rpc.shutdown()
                return


if __name__ == "__main__":
    main()
