import { app, shell, BrowserWindow, screen, Tray, Menu, nativeImage } from "electron";

// Only one Executor instance.
const boolGotLock = app.requestSingleInstanceLock();
if (!boolGotLock) {
  console.log("Another Executor has been running.");

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

import { loggerMain } from "./Logging/logger";
import { strDefaultProjectLogFolderPath } from "./Config/basicConfig";
import { dictConfigExecutor } from "./Config/executorConfig";
import { closeDatabase, initializeDatabase } from "./Database/connection";
import { dbMarkRunningRunsInterrupted } from "./Database/runHistoryRepository";
import { recoverProjectPackageImports } from "./Package/packageImportTransaction";
import { recoverProjectPackageDeletions } from "./Package/projectInstallation";
import {
  setResolution,
  startRdpSessionManager,
  stopRdpSessionManager,
} from "./Rdp/rdpSession";
import { registerExecutorIpc } from "./IPC/ipc";
import { sendMainMessage } from "./IPC/mainMessage";
import { onRunEnded } from "./Run/lifecycle";
import { startRunHousekeeping } from "./Run/housekeeping";
import { shutdownProjectRuns } from "./Run/projectRunner";
import {
  getRunQueueItems,
  onRunQueueChanged,
  startSchedulerEngine,
  stopSchedulerEngine,
} from "./Scheduler/schedulerEngine";
import type { DictMainMessage } from "../shared/ipc";

initializeDatabase();
recoverProjectPackageImports();
recoverProjectPackageDeletions();
dbMarkRunningRunsInterrupted();

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let boolAppQuitting = false;
let boolShutdownStarted = false;
let boolShutdownComplete = false;

function sendMessageToRenderer(message: DictMainMessage): void {
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
    // autoHideMenuBar: false,
    autoHideMenuBar: true,
    icon: icon,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const webContentsObj = mainWindow.webContents;

  webContentsObj.on("did-finish-load", () => {
    // Open DevTools when the content finishes loading.
    // NOTE: delete it before packaging.
    // webContentsObj.openDevTools();

    sendMainMessage(webContentsObj, {
      type: "initializeSetting",
      data: {
        config: dictConfigExecutor,
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
    loggerMain.info("Open: " + details.url);
    // Open the URL in the user's default browser
    void shell.openExternal(details.url).catch((e: unknown) => {
      loggerMain.error(`Failed to open URL ${details.url}: ${String(e)}`);
    });
    // Deny creating a new window in the app
    return { action: "deny" };
  });

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    loggerMain.info("development mode");
    void mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]).catch((e: unknown) => {
      loggerMain.error(`Failed to load the development Renderer: ${String(e)}`);
    });
  } else {
    loggerMain.info("production mode");
    void mainWindow
      .loadFile(join(__dirname, "../renderer/index.html"))
      .catch((e: unknown) => {
        loggerMain.error(`Failed to load the packaged Renderer: ${String(e)}`);
      });
  }
}

// This method will be called when Electron has finished initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
void app
  .whenReady()
  .then(() => {
    // Set app user model id for windows
    electronApp.setAppUserModelId("com.liberrpa.executor");

    // build our tray icon
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

    // clicking the icon toggles the window
    tray.on("click", (): void => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
        }
      }
    });

    const displays = screen.getAllDisplays();
    if (displays.length === 0) {
      loggerMain.info("Have no screen.");
    } else {
      const mainDisplay = displays.find(
        (display) => display.bounds.x === 0 && display.bounds.y === 0,
      );
      if (!mainDisplay) {
        throw new Error("Not found main screen.");
      } else {
        screen.on("display-metrics-changed", () => {
          const { width, height } = screen.getPrimaryDisplay().size;
          loggerMain.info(`Display metrics changed. Resolution: ${width}x${height}`);
          if (
            dictConfigExecutor.keepRdpSession &&
            (width !== dictConfigExecutor.keepRdpSessionWidth ||
              height !== dictConfigExecutor.keepRdpSessionHeight)
          ) {
            loggerMain.info("Need to set resolution.");
            // NOTE: It not works in Hyper-V Enhenced session.
            setResolution(
              dictConfigExecutor.keepRdpSessionWidth,
              dictConfigExecutor.keepRdpSessionHeight,
            );
          }
        });
      }
    }

    // Default open or close DevTools by F12 in development and ignore CommandOrControl + R in production. See https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
    app.on("browser-window-created", (_event, window) => {
      optimizer.watchWindowShortcuts(window);
    });

    registerExecutorIpc(() => mainWindow?.webContents);

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

    app.on("activate", function () {
      // On macOS it's common to re-create a window in the app when the dock icon is clicked and there are no other windows open.
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  })
  .catch((e: unknown) => {
    loggerMain.error(`Failed to initialize Executor: ${String(e)}`);
    app.quit();
  });

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
  stopSchedulerEngine();
  stopRdpSessionManager();

  void shutdownProjectRuns()
    .catch((e: unknown) => {
      loggerMain.error(`Failed to stop active Project Runs: ${String(e)}`);
    })
    .finally(() => {
      closeDatabase();
      boolShutdownComplete = true;
      app.quit();
    });
});

// Quit when all windows are closed, except on macOS. There, it's common for applications and their menu bar to stay active until the user quits explicitly with Cmd + Q.
app.on("window-all-closed", () => {
  loggerMain.info("Executor window closed.");
  if (process.platform !== "darwin") {
    app.quit();
  }
});
