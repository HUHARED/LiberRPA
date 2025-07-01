// FileName: rdpSessionFunc.ts

import { is } from "@electron-toolkit/utils";
import { spawn, ChildProcessWithoutNullStreams } from "child_process";
import path from "path";

import { loggerMain } from "./logger";
import { dictConfigExecutor, strPyEnvPath } from "./commonFunc";

function getScriptFolderPath(): string {
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    return path.join(__dirname, "../../resources/pyRdpScript");
  } else {
    return path.join(process.resourcesPath, "app.asar.unpacked/resources/pyRdpScript");
  }
}

const strScriptFolderPath = getScriptFolderPath();

export async function runSessionListener(): Promise<void> {
  loggerMain.debug("--runSessionListener--");

  const strScriptPath = path.join(strScriptFolderPath, "ListenSession.py");

  const processPySessionListener = spawn(
    path.join(strPyEnvPath, "python.exe"),
    [strScriptPath],
    {
      env: {
        PATH: [
          strPyEnvPath,
          path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
          path.join(strPyEnvPath, "Library", "usr", "bin"),
          path.join(strPyEnvPath, "Library", "bin"),
          path.join(strPyEnvPath, "Scripts"),
          path.join(strPyEnvPath, "bin"),
          process.env.PATH,
        ].join(";"),
        PYTHONPATH: [strScriptFolderPath].join(";"),
        ...process.env,
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

  let strEventCache: string = "";

  processPySessionListener.stdout.on("data", (data) => {
    loggerMain.debug(`[ListenSession] ${data}`);

    const strTextTemp: string = data.toString().trim();

    if (strTextTemp === "Detected session lock event.") {
      strEventCache = "session lock";
    } else if (strTextTemp === "Detected session unlock event.") {
      strEventCache = "session unlock";
    } else if (strTextTemp === "Detected console disconnect event.") {
      strEventCache = "console disconnect";
    } else if (strTextTemp === "Detected console connect event.") {
      strEventCache = "console connect";
    } else if (strTextTemp === "Detected RDP connect event.") {
      strEventCache = "RDP connect";
    }

    // The current event is "RDP disconnect", then check the previous event, if it matches some rules, set session(including set resolution).
    if (strTextTemp === "Detected RDP disconnect event.") {
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
    }
  });

  processPySessionListener.stderr.on("data", (data) => {
    loggerMain.error(`[ListenSession] ${data}`);
  });

  processPySessionListener.on("close", (code) => {
    loggerMain.info(`[ListenSession] Exited with code ${code}`);
  });

  // End the function but not stop the listener.
  return;
}

async function setSession(): Promise<void> {
  loggerMain.debug("--setSession--");

  const strScriptPath = path.join(strScriptFolderPath, "SetSession.py");

  const processPySetSession = spawn(
    path.join(strPyEnvPath, "python.exe"),
    [strScriptPath],
    {
      env: {
        PATH: [
          strPyEnvPath,
          path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
          path.join(strPyEnvPath, "Library", "usr", "bin"),
          path.join(strPyEnvPath, "Library", "bin"),
          path.join(strPyEnvPath, "Scripts"),
          path.join(strPyEnvPath, "bin"),
          process.env.PATH,
        ].join(";"),
        PYTHONPATH: [strScriptFolderPath].join(";"),
        ...process.env,
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

  processPySetSession.stdout.on("data", (data) => {
    loggerMain.debug(`[SetSession] ${data}`);
  });

  processPySetSession.stderr.on("data", (data) => {
    loggerMain.error(`[SetSession] ${data}`);
  });

  processPySetSession.on("close", (code) => {
    loggerMain.info(`[SetSession] Exited with code ${code}`);
  });

  // End the function but not stop the listener.
  return;
}

export async function setResolution(width: number, height: number): Promise<void> {
  loggerMain.debug("--setResolution--");

  const strScriptPath = path.join(strScriptFolderPath, "SetResolution.py");

  const processPySetResolution = spawn(
    path.join(strPyEnvPath, "python.exe"),
    [strScriptPath, "--width", width.toString(), "--height", height.toString()],
    {
      env: {
        PATH: [
          strPyEnvPath,
          path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
          path.join(strPyEnvPath, "Library", "usr", "bin"),
          path.join(strPyEnvPath, "Library", "bin"),
          path.join(strPyEnvPath, "Scripts"),
          path.join(strPyEnvPath, "bin"),
          process.env.PATH,
        ].join(";"),
        PYTHONPATH: [strScriptFolderPath].join(";"),
        ...process.env,
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

  processPySetResolution.stdout.on("data", (data) => {
    loggerMain.debug(`[SetResolution] ${data}`);
  });

  processPySetResolution.stderr.on("data", (data) => {
    loggerMain.error(`[SetResolution] ${data}`);
  });

  processPySetResolution.on("close", (code) => {
    loggerMain.info(`[SetResolution] Exited with code ${code}`);
  });

  // End the function but not stop the listener.
  return;
}

/* Manage the mouse move logic. */
let processPyMoveMouse: ChildProcessWithoutNullStreams | undefined = undefined;

setInterval(() => {
  if (dictConfigExecutor.keepRdpSession) {
    if (!processPyMoveMouse) {
      moveMouse();
    }
  }
}, 1000);

function moveMouse(): void {
  loggerMain.debug("--moveMouse--");

  const strScriptPath = path.join(strScriptFolderPath, "MoveMouse.py");

  processPyMoveMouse = spawn(path.join(strPyEnvPath, "python.exe"), [strScriptPath], {
    env: {
      PATH: [
        strPyEnvPath,
        path.join(strPyEnvPath, "Library", "mingw-w64", "bin"),
        path.join(strPyEnvPath, "Library", "usr", "bin"),
        path.join(strPyEnvPath, "Library", "bin"),
        path.join(strPyEnvPath, "Scripts"),
        path.join(strPyEnvPath, "bin"),
        process.env.PATH,
      ].join(";"),
      PYTHONPATH: [strScriptFolderPath].join(";"),
      ...process.env,
    },
    stdio: ["pipe", "pipe", "pipe"],
  });

  processPyMoveMouse.stdout.on("data", (data) => {
    loggerMain.debug(`[MoveMouse] ${data}`);
  });

  processPyMoveMouse.stderr.on("data", (data) => {
    loggerMain.error(`[MoveMouse] ${data}`);
  });

  processPyMoveMouse.on("close", (code) => {
    loggerMain.info(`[MoveMouse] Exited with code ${code}`);
    processPyMoveMouse = undefined;
  });

  const intervalInner = setInterval(() => {
    // Stop the process if didn't need to move mouse.
    if (!dictConfigExecutor.keepRdpSession && processPyMoveMouse) {
      processPyMoveMouse.stdin.write("Executor-terminated\n");
      processPyMoveMouse.stdin.end();
      clearInterval(intervalInner);
    }
  }, 1000);

  // End the function but not stop the listener.
  return;
}
