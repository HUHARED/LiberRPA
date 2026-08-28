// FileName: rdpSession.ts

import { is } from "@electron-toolkit/utils";
import { spawn } from "child_process";
import type { ChildProcessWithoutNullStreams } from "child_process";
import path from "path";
import { createInterface } from "readline";

import { getErrorMessage } from "../../shared/error";
import { isProcessRunning } from "../Common/process";
import { dictConfigExecutor } from "../Config/executorConfig";
import {
  buildPythonProcessEnvironment,
  strDefaultPythonEnvironmentPath,
} from "../Config/environment";
import { loggerMain } from "../Logging/logger";

const STR_MOVE_MOUSE_TERMINATION_MESSAGE = "Executor-stop-move-mouse";
const INT_RDP_HELPER_CHECK_INTERVAL_MS = 1000;
const INT_RDP_HELPER_TERMINATION_WAIT_MS = 3 * 1000;
const setRdpProcess = new Set<ChildProcessWithoutNullStreams>();

function getScriptFolderPath(): string {
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    return path.join(__dirname, "../../resources/pyRdpScript");
  }
  return path.join(process.resourcesPath, "app.asar.unpacked/resources/pyRdpScript");
}

const strScriptFolderPath = getScriptFolderPath();

function spawnRdpScript(
  scriptName: string,
  argumentArr: string[] = [],
): ChildProcessWithoutNullStreams {
  const strScriptPath = path.join(strScriptFolderPath, scriptName);
  const processPy = spawn(
    path.join(strDefaultPythonEnvironmentPath, "python.exe"),
    [strScriptPath, ...argumentArr],
    {
      env: buildPythonProcessEnvironment({
        pythonEnvironmentPath: strDefaultPythonEnvironmentPath,
        pythonPathEntries: [strScriptFolderPath],
      }),
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  setRdpProcess.add(processPy);
  processPy.once("close", () => {
    setRdpProcess.delete(processPy);
  });
  processPy.once("error", (e: Error) => {
    loggerMain.error(`[${scriptName}] Process error: ${e.message}`);
  });
  processPy.stdin.on("error", (e: Error) => {
    loggerMain.debug(`[${scriptName}] stdin closed: ${e.message}`);
  });

  return processPy;
}

function attachLineLogging(processPy: ChildProcessWithoutNullStreams, label: string): void {
  const stdoutReader = createInterface({ input: processPy.stdout });
  const stderrReader = createInterface({ input: processPy.stderr });

  stdoutReader.on("line", (strLine) => {
    loggerMain.debug(`[${label}] ${strLine}`);
  });
  stderrReader.on("line", (strLine) => {
    loggerMain.error(`[${label}] ${strLine}`);
  });
}

let boolRdpSessionManagerStarted = false;
let processPySessionListener: ChildProcessWithoutNullStreams | undefined;
let processPyMoveMouse: ChildProcessWithoutNullStreams | undefined;
let boolMoveMouseTerminationRequested = false;
let timerRdpHelperCheck: NodeJS.Timeout | undefined;

function startSessionListener(): void {
  if (
    processPySessionListener !== undefined &&
    isProcessRunning(processPySessionListener)
  ) {
    return;
  }

  loggerMain.debug("--startSessionListener--");
  const processPy = spawnRdpScript("ListenSession.py");
  processPySessionListener = processPy;

  let strEventCache = "";
  const stdoutReader = createInterface({ input: processPy.stdout });
  const stderrReader = createInterface({ input: processPy.stderr });

  stdoutReader.on("line", (strLine) => {
    loggerMain.debug(`[ListenSession] ${strLine}`);

    if (strLine === "Detected session lock event.") {
      strEventCache = "session lock";
    } else if (strLine === "Detected session unlock event.") {
      strEventCache = "session unlock";
    } else if (strLine === "Detected console disconnect event.") {
      strEventCache = "console disconnect";
    } else if (strLine === "Detected console connect event.") {
      strEventCache = "console connect";
    } else if (strLine === "Detected RDP connect event.") {
      strEventCache = "RDP connect";
    }

    if (strLine !== "Detected RDP disconnect event.") {
      return;
    }
    if (!dictConfigExecutor.keepRdpSession) {
      loggerMain.debug("RDP session preservation is disabled.");
      return;
    }
    if (strEventCache === "RDP connect") {
      loggerMain.debug(
        "A manually connected basic session does not require Session switching.",
      );
      return;
    }
    if (strEventCache === "console connect") {
      loggerMain.debug(
        "A manually connected enhanced session does not require Session switching.",
      );
      return;
    }

    setSession();
  });

  stderrReader.on("line", (strLine) => {
    loggerMain.error(`[ListenSession] ${strLine}`);
  });

  processPy.once("close", (intExitCode, strSignal) => {
    loggerMain.info(
      `[ListenSession] Exited with code ${String(intExitCode)}, signal ${String(strSignal)}`,
    );
    if (processPySessionListener === processPy) {
      processPySessionListener = undefined;
    }
  });
}

function setSession(): void {
  loggerMain.debug("--setSession--");
  const processPy = spawnRdpScript("SetSession.py");
  attachLineLogging(processPy, "SetSession");
  processPy.once("close", (intExitCode, strSignal) => {
    loggerMain.info(
      `[SetSession] Exited with code ${String(intExitCode)}, signal ${String(strSignal)}`,
    );
  });
}

export function setResolution(width: number, height: number): void {
  loggerMain.debug("--setResolution--");
  const processPy = spawnRdpScript("SetResolution.py", [
    "--width",
    width.toString(),
    "--height",
    height.toString(),
  ]);
  attachLineLogging(processPy, "SetResolution");
  processPy.once("close", (intExitCode, strSignal) => {
    loggerMain.info(
      `[SetResolution] Exited with code ${String(intExitCode)}, signal ${String(strSignal)}`,
    );
  });
}

function startMoveMouse(): void {
  if (processPyMoveMouse !== undefined && isProcessRunning(processPyMoveMouse)) {
    return;
  }

  loggerMain.debug("--startMoveMouse--");
  const processPy = spawnRdpScript("MoveMouse.py");
  processPyMoveMouse = processPy;
  boolMoveMouseTerminationRequested = false;
  attachLineLogging(processPy, "MoveMouse");

  processPy.once("close", (intExitCode, strSignal) => {
    loggerMain.info(
      `[MoveMouse] Exited with code ${String(intExitCode)}, signal ${String(strSignal)}`,
    );
    if (processPyMoveMouse === processPy) {
      processPyMoveMouse = undefined;
      boolMoveMouseTerminationRequested = false;
    }
  });
}

function requestMoveMouseTermination(): boolean {
  const processPy = processPyMoveMouse;
  if (
    processPy === undefined ||
    !isProcessRunning(processPy) ||
    boolMoveMouseTerminationRequested ||
    processPy.stdin.destroyed ||
    !processPy.stdin.writable
  ) {
    return false;
  }

  try {
    processPy.stdin.end(`${STR_MOVE_MOUSE_TERMINATION_MESSAGE}\n`);
    boolMoveMouseTerminationRequested = true;
    return true;
  } catch (e: unknown) {
    loggerMain.error(`Failed to request MoveMouse termination: ${getErrorMessage(e)}`);
    return false;
  }
}

function waitForRdpProcessClose(
  processPy: ChildProcessWithoutNullStreams,
): Promise<boolean> {
  if (!isProcessRunning(processPy)) {
    return Promise.resolve(true);
  }

  return new Promise<boolean>((resolve) => {
    const handleClose = (): void => {
      clearTimeout(timerTimeout);
      resolve(true);
    };

    const timerTimeout = setTimeout(() => {
      processPy.removeListener("close", handleClose);
      resolve(!isProcessRunning(processPy));
    }, INT_RDP_HELPER_TERMINATION_WAIT_MS);

    processPy.once("close", handleClose);
  });
}

async function stopRdpProcess(
  processPy: ChildProcessWithoutNullStreams,
  boolWaitForGracefulTermination: boolean,
): Promise<void> {
  if (!isProcessRunning(processPy)) {
    return;
  }

  if (boolWaitForGracefulTermination && (await waitForRdpProcessClose(processPy))) {
    return;
  }

  try {
    processPy.kill();
  } catch (e: unknown) {
    loggerMain.error(
      `Failed to terminate RDP helper process ${String(processPy.pid)}: ${getErrorMessage(
        e,
      )}`,
    );
    return;
  }

  if (!(await waitForRdpProcessClose(processPy))) {
    loggerMain.error(
      `RDP helper process ${String(processPy.pid)} remained active after termination.`,
    );
  }
}

function syncRdpHelperProcesses(): void {
  if (!boolRdpSessionManagerStarted) {
    return;
  }

  if (
    processPySessionListener === undefined ||
    !isProcessRunning(processPySessionListener)
  ) {
    startSessionListener();
  }

  if (dictConfigExecutor.keepRdpSession) {
    if (processPyMoveMouse === undefined || !isProcessRunning(processPyMoveMouse)) {
      startMoveMouse();
    }
    return;
  }

  requestMoveMouseTermination();
}

export function startRdpSessionManager(): void {
  if (boolRdpSessionManagerStarted) {
    return;
  }

  loggerMain.debug("--startRdpSessionManager--");
  boolRdpSessionManagerStarted = true;
  syncRdpHelperProcesses();
  timerRdpHelperCheck = setInterval(
    syncRdpHelperProcesses,
    INT_RDP_HELPER_CHECK_INTERVAL_MS,
  );
}

export async function stopRdpSessionManager(): Promise<void> {
  if (
    !boolRdpSessionManagerStarted &&
    timerRdpHelperCheck === undefined &&
    setRdpProcess.size === 0
  ) {
    return;
  }

  loggerMain.debug("--stopRdpSessionManager--");
  boolRdpSessionManagerStarted = false;

  if (timerRdpHelperCheck !== undefined) {
    clearInterval(timerRdpHelperCheck);
    timerRdpHelperCheck = undefined;
  }

  const processMoveMouse = processPyMoveMouse;
  const boolMoveMouseTerminationRequestedNow = requestMoveMouseTermination();
  const boolWaitForMoveMouse =
    boolMoveMouseTerminationRequestedNow || boolMoveMouseTerminationRequested;
  const arrProcess = [...setRdpProcess];

  await Promise.all(
    arrProcess.map((processPy) =>
      stopRdpProcess(processPy, processPy === processMoveMouse && boolWaitForMoveMouse),
    ),
  );
}
