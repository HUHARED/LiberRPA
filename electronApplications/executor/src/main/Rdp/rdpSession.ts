import { is } from "@electron-toolkit/utils";
import { spawn } from "child_process";
import type { ChildProcessWithoutNullStreams } from "child_process";
import path from "path";
import { createInterface } from "readline";

import { dictConfigExecutor } from "../Config/executorConfig";
import {
  getPythonProcessEnvironment,
  strDefaultPythonEnvironmentPath,
} from "../Config/environment";
import { loggerMain } from "../Logging/logger";

const STR_MOVE_MOUSE_TERMINATION_MESSAGE = "Executor-stop-move-mouse";
const INT_RDP_HELPER_CHECK_INTERVAL_MS = 1000;

function getScriptFolderPath(): string {
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    return path.join(__dirname, "../../resources/pyRdpScript");
  }
  return path.join(process.resourcesPath, "app.asar.unpacked/resources/pyRdpScript");
}

const strScriptFolderPath = getScriptFolderPath();

function isProcessRunning(processPy: ChildProcessWithoutNullStreams): boolean {
  return processPy.exitCode === null && processPy.signalCode === null;
}

function spawnRdpScript(
  strScriptName: string,
  arrArgument: string[] = [],
): ChildProcessWithoutNullStreams {
  const strScriptPath = path.join(strScriptFolderPath, strScriptName);
  const processPy = spawn(
    path.join(strDefaultPythonEnvironmentPath, "python.exe"),
    [strScriptPath, ...arrArgument],
    {
      env: getPythonProcessEnvironment({
        pythonEnvironmentPath: strDefaultPythonEnvironmentPath,
        pythonPathEntries: [strScriptFolderPath],
      }),
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  processPy.once("error", (e: Error) => {
    loggerMain.error(`[${strScriptName}] Process error: ${e.message}`);
  });
  processPy.stdin.on("error", (e: Error) => {
    loggerMain.debug(`[${strScriptName}] stdin closed: ${e.message}`);
  });

  return processPy;
}

function attachLineLogging(
  processPy: ChildProcessWithoutNullStreams,
  strLabel: string,
): void {
  const stdoutReader = createInterface({ input: processPy.stdout });
  const stderrReader = createInterface({ input: processPy.stderr });

  stdoutReader.on("line", (strLine) => {
    loggerMain.debug(`[${strLabel}] ${strLine}`);
  });
  stderrReader.on("line", (strLine) => {
    loggerMain.error(`[${strLabel}] ${strLine}`);
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
      loggerMain.debug("Not need to keep RDP session.");
      return;
    }
    if (strEventCache === "RDP connect") {
      loggerMain.debug("It is manual basic session, not need to set session.");
      return;
    }
    if (strEventCache === "console connect") {
      loggerMain.debug("It is manual enhanced session, not need to set session.");
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

function requestMoveMouseTermination(): void {
  const processPy = processPyMoveMouse;
  if (
    processPy === undefined ||
    !isProcessRunning(processPy) ||
    boolMoveMouseTerminationRequested
  ) {
    return;
  }

  boolMoveMouseTerminationRequested = true;
  processPy.stdin.write(`${STR_MOVE_MOUSE_TERMINATION_MESSAGE}\n`);
  processPy.stdin.end();
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

export function stopRdpSessionManager(): void {
  if (!boolRdpSessionManagerStarted) {
    return;
  }

  loggerMain.debug("--stopRdpSessionManager--");
  boolRdpSessionManagerStarted = false;

  if (timerRdpHelperCheck !== undefined) {
    clearInterval(timerRdpHelperCheck);
    timerRdpHelperCheck = undefined;
  }

  if (
    processPySessionListener !== undefined &&
    isProcessRunning(processPySessionListener)
  ) {
    processPySessionListener.kill();
  }
  if (processPyMoveMouse !== undefined && isProcessRunning(processPyMoveMouse)) {
    processPyMoveMouse.kill();
  }
}
