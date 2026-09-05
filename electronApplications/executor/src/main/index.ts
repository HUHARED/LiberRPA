// FileName: index.ts

import { app, shell, BrowserWindow, screen, Tray, Menu, nativeImage } from "electron";

// Only one Executor instance.
const boolGotLock = app.requestSingleInstanceLock();
if (!boolGotLock) {
  console.log("Another Executor instance is already running.");

  app.quit();
  process.exit(0);
}

// Focus on the existing window.
app.on("second-instance", (_event, _argv, _cwd) => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

import { join } from "path";
import { electronApp, optimizer, is } from "@electron-toolkit/utils";
import icon from "../../resources/LiberRPA_icon_v3_color_Executor_256.ico?asset";

import { getErrorMessage } from "../shared/error";
import { loggerMain } from "./Logging/logger";
import { strDefaultProjectLogFolderPath } from "./Config/basicConfig";
import { dictConfigExecutor } from "./Config/executorConfig";
import { closeDatabase, initializeDatabase } from "./Database/connection";
import { dbMarkRunningRunsInterrupted } from "./Database/runHistoryRepository";
import { recoverProjectPackageInstallations } from "./Package/packageInstallationTransaction";
import { recoverProjectPackageDeletions } from "./Package/projectDeletion";
import { startRdpSessionManager, stopRdpSessionManager } from "./Rdp/rdpSession";
import { registerExecutorIpc } from "./IPC/ipc";
import { sendMainMessage } from "./IPC/mainMessage";
import { onRunEnded } from "./Run/lifecycle";
import { startRunHousekeeping, stopRunHousekeeping } from "./Run/housekeeping";
import { beginProjectRunShutdown, shutdownProjectRuns } from "./Run/projectRunner";
import {
  getRunQueueItems,
  onRunQueueChanged,
  startSchedulerEngine,
  stopSchedulerEngine,
} from "./Scheduler/schedulerEngine";
import type { Dict_Message_Main } from "../shared/ipc";

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let boolAppQuitting = false;
let boolShutdownStarted = false;
let boolShutdownComplete = false;

function sendMessageToRenderer(message: Dict_Message_Main): void {
  if (boolAppQuitting) {
    return;
  }

  const webContentsObj = mainWindow?.webContents;
  if (webContentsObj !== undefined) {
    sendMainMessage(webContentsObj, message);
  }
}

function createWindow(): void {
  loggerMain.debug("--createWindow--");
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1280,
    minHeight: 800,
    show: false,
    autoHideMenuBar: true,
    icon: icon,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  const webContentsObj = mainWindow.webContents;

  webContentsObj.on("did-finish-load", () => {
    if (boolAppQuitting) {
      return;
    }

    sendMainMessage(webContentsObj, {
      type: "initializeSetting",
      data: {
        configDict: dictConfigExecutor,
        defaultProjectLogFolderPath: strDefaultProjectLogFolderPath,
      },
    });
    sendMainMessage(webContentsObj, {
      type: "runQueueChanged",
      data: { items: getRunQueueItems() },
    });
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.on("close", (event) => {
    if (!boolAppQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  webContentsObj.setWindowOpenHandler((details) => {
    let urlObj: URL;
    try {
      urlObj = new URL(details.url);
    } catch (e: unknown) {
      loggerMain.warn(`Reject invalid external URL: ${getErrorMessage(e)}`);
      return { action: "deny" };
    }

    if (urlObj.protocol !== "https:" && urlObj.protocol !== "http:") {
      loggerMain.warn(`Reject unsupported external URL scheme: ${urlObj.protocol}`);
      return { action: "deny" };
    }

    loggerMain.info(`Open external URL: ${urlObj.href}`);
    void shell.openExternal(urlObj.href).catch((e: unknown) => {
      loggerMain.error(`Failed to open URL ${urlObj.href}: ${getErrorMessage(e)}`);
    });
    return { action: "deny" };
  });

  // Support Renderer HMR through electron-vite.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    loggerMain.info("development mode");
    void mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]).catch((e: unknown) => {
      loggerMain.error(`Failed to load the development Renderer: ${getErrorMessage(e)}`);
    });
  } else {
    loggerMain.info("production mode");
    void mainWindow
      .loadFile(join(__dirname, "../renderer/index.html"))
      .catch((e: unknown) => {
        loggerMain.error(`Failed to load the packaged Renderer: ${getErrorMessage(e)}`);
      });
  }
}

void app
  .whenReady()
  .then(() => {
    initializeDatabase();
    recoverProjectPackageInstallations();
    recoverProjectPackageDeletions();
    dbMarkRunningRunsInterrupted();

    // Set the Windows application user model ID.
    electronApp.setAppUserModelId("com.liberrpa.executor");

    // Create the tray icon.
    const trayIcon = nativeImage.createFromPath(icon);
    tray = new Tray(trayIcon);

    const trayMenu = Menu.buildFromTemplate([
      {
        label: "Show",
        click: (): void => {
          mainWindow?.show();
        },
      },
      {
        label: "Exit",
        click: (): void => {
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(trayMenu);
    tray.setToolTip("LiberRPA Executor");

    // Toggle the window when the tray icon is clicked.
    tray.on("click", (): void => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
        }
      }
    });

    if (screen.getAllDisplays().length === 0) {
      loggerMain.info("No display is available.");
    } else {
      screen.on("display-metrics-changed", () => {
        const { width, height } = screen.getPrimaryDisplay().size;
        loggerMain.info(`Primary display metrics changed. Resolution: ${width}x${height}`);
      });
    }

    // Configure standard development and production window shortcuts.
    app.on("browser-window-created", (_event, window) => {
      optimizer.watchWindowShortcuts(window);
    });

    registerExecutorIpc(
      () => mainWindow?.webContents,
      () => boolShutdownStarted,
    );

    createWindow();

    onRunEnded(() => {
      sendMessageToRenderer({ type: "runEnded" });
    });
    onRunQueueChanged((arrItem) => {
      sendMessageToRenderer({
        type: "runQueueChanged",
        data: { items: arrItem },
      });
    });
    startRunHousekeeping();
    startSchedulerEngine();
    startRdpSessionManager();
  })
  .catch((e: unknown) => {
    loggerMain.error(`Failed to initialize Executor: ${getErrorMessage(e)}`);
    app.quit();
  });

async function shutdownExecutor(): Promise<void> {
  try {
    await stopSchedulerEngine();
  } catch (e: unknown) {
    loggerMain.error(`Failed to stop Scheduler engine: ${getErrorMessage(e)}`);
  }

  try {
    await stopRdpSessionManager();
  } catch (e: unknown) {
    loggerMain.error(`Failed to stop RDP helper processes: ${getErrorMessage(e)}`);
  }

  try {
    await shutdownProjectRuns();
  } catch (e: unknown) {
    loggerMain.error(`Failed to stop active Project Runs: ${getErrorMessage(e)}`);
  }

  try {
    closeDatabase();
  } catch (e: unknown) {
    loggerMain.error(`Failed to close Executor database: ${getErrorMessage(e)}`);
  } finally {
    boolShutdownComplete = true;
    app.quit();
  }
}

app.on("before-quit", (event) => {
  boolAppQuitting = true;

  if (boolShutdownComplete) {
    return;
  }

  event.preventDefault();
  if (boolShutdownStarted) {
    return;
  }

  boolShutdownStarted = true;
  beginProjectRunShutdown();
  stopRunHousekeeping();
  void shutdownExecutor();
});

app.on("window-all-closed", () => {
  loggerMain.info("Executor window closed.");
  app.quit();
});
