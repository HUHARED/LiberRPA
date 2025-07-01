// FileName: index.ts
import {
  app,
  shell,
  BrowserWindow,
  ipcMain,
  screen,
  Tray,
  Menu,
  nativeImage,
} from "electron";

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

import { loggerMain } from "./logger";
import {
  dictConfigBasic,
  dictConfigExecutor,
  saveExecutorConfigDict,
  selectProjectLogFolder,
} from "./commonFunc";
import {
  initializeTables,
  dbSelectProjectNames,
  dbSelectProjectVersions,
  dbSelectProjectDetail,
  dbInsertProjectDetail,
  dbInsertSchedulerDetail,
  dbUpdateProjectDetail,
  dbSelectProjectBindSchedulers,
  dbDeleteProject,
  dbSelectSchedulerList,
  dbSelectSchedulerDetail,
  dbUpdateSchedulerDetail,
  dbDeleteScheduler,
  dbSelectLimitHistoryList,
  dbSelectCountHistoryRunning,
  dbSelectProjectNewestVersionDetail,
  dbUpdateHistoryDetail_unknown,
} from "./database";
import {
  fileSelectPackageAndExtractToTempFolder,
  fileDeleteTempFolder,
  fileMoveTempFilesToExecutorPackage,
  fileDeleteExecutorPackage,
  fileOpenFolder,
} from "./fileFunc";
import { pythonRun, pythonCancel } from "./pythonFunc";
import {
  logCleanFolderByTimeout,
  logCleanVideoByTimeout,
  logCleanVideoBySize,
} from "./logCleanFunc";
import { runSessionListener, setResolution } from "./rdpSessionFunc";
import { DictInvokeResult, DictExecutorConfig } from "../shared/interface";

initializeTables();
dbUpdateHistoryDetail_unknown();

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let webContentsObj: Electron.WebContents;

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
      sandbox: false,
    },
  });

  webContentsObj = mainWindow.webContents;

  webContentsObj.on("did-finish-load", () => {
    // Open DevTools when the content finishes loading.
    // NOTE: delete it before packaging.
    // webContentsObj.openDevTools();

    if (dictConfigExecutor["projectLogFolderPath"] === "") {
      dictConfigExecutor["projectLogFolderPath"] = dictConfigBasic["outputLogPath"].replace(
        "\\BuildinTools",
        "\\Executor"
      );
    }

    webContentsObj.send("send-from-main", "init-setting", dictConfigExecutor);
    runSessionListener();
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.on("close", (event) => {
    if (!(app as any).isQuitting) {
      // Otherwise a complaint will appear: Property 'isQuitting' does not exist on type 'App'.ts(2339)
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  webContentsObj.setWindowOpenHandler((details) => {
    loggerMain.info("Open: " + details.url);
    // Open the URL in the user's default browser
    shell.openExternal(details.url);
    // Deny creating a new window in the app
    return { action: "deny" };
  });

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    loggerMain.info("development mode");
    mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    loggerMain.info("production mode");
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

// This method will be called when Electron has finished initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
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
        (app as any).isQuitting = true;
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
      (display) => display.bounds.x === 0 && display.bounds.y === 0
    );
    if (!mainDisplay) {
      throw new Error("Not found main screen.");
    } else {
      screen.on("display-metrics-changed", () => {
        const { width, height } = screen.getPrimaryDisplay().size;
        loggerMain.info(`Display metrics changed. Resolution: ${width}x${height}`);
        if (
          dictConfigExecutor.keepRdpSession &&
          width !== dictConfigExecutor.keepRdpSessionWidth &&
          height !== dictConfigExecutor.keepRdpSessionHeight
        ) {
          loggerMain.info("Need to set resolution.");
          // NOTE: It not works in Hyper-V Enhenced session.
          setResolution(
            dictConfigExecutor.keepRdpSessionWidth,
            dictConfigExecutor.keepRdpSessionHeight
          );
        }
      });
    }
  }

  // Default open or close DevTools by F12 in development and ignore CommandOrControl + R in production. See https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on("browser-window-created", (_event, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  ipcMain.on("send-from-renderer-log", (_event, { level, message }) =>
    loggerMain.log(level, "[Renderer] " + message)
  );

  ipcMain.on("send-from-renderer", (_event, command: string, data?: any): void => {
    loggerMain.debug(`[send-from-renderer] (${command}) ${JSON.stringify(data, null, 2)}`);
    try {
      switch (command) {
        /* Setting */
        case "send:open-project-log-folder-path":
          openProjectLogFolderPath(data);
          break;

        case "send:save-executor-config":
          saveExecutorConfigDict(data);
          // Update dictConfigExecutor due to other modules need it.
          for (const [key, value] of Object.entries(data as DictExecutorConfig)) {
            dictConfigExecutor[key] = value;
          }
          break;

        default:
          loggerMain.error(`An unidentified command in send-from-renderer: ${command}.`);
          break;
      }
    } catch (err) {
      loggerMain.error(`Error running command: ${command}`, err);
    }
  });

  ipcMain.handle(
    "invoke-from-renderer",
    async (_event, command: string, data?: any): Promise<DictInvokeResult> => {
      loggerMain.debug(
        `[invoke-from-renderer] (${command}) ${JSON.stringify(data, null, 2)}`
      );
      try {
        let temp: any;
        switch (command) {
          /* Multiple modules need. */

          case "invoke:pythonRun": {
            temp = await pythonRun(data, webContentsObj);
            break;
          }

          /* Project Local Package */

          case "invoke:fileSelectPackageAndExtractToTempFolder": {
            temp = await fileSelectPackageAndExtractToTempFolder();
            break;
          }

          case "invoke:fileDeleteTempFolder": {
            temp = await fileDeleteTempFolder();
            break;
          }

          case "invoke:fileMoveTempFilesToExecutorPackage": {
            temp = await fileMoveTempFilesToExecutorPackage(data.name, data.version);
            break;
          }

          case "invoke:fileDeleteExecutorPackage": {
            temp = await fileDeleteExecutorPackage(data.name, data.version);
            break;
          }

          case "invoke:dbSelectProjectNames": {
            temp = dbSelectProjectNames();
            break;
          }

          case "invoke:dbSelectProjectVersions": {
            temp = dbSelectProjectVersions(data);
            break;
          }

          case "invoke:dbSelectProjectDetail": {
            temp = dbSelectProjectDetail(data.name, data.version);
            break;
          }

          case "invoke:dbInsertProjectDetail": {
            temp = dbInsertProjectDetail(data);
            break;
          }

          case "invoke:dbUpdateProjectDetail": {
            temp = dbUpdateProjectDetail(data);
            break;
          }

          case "invoke:dbSelectProjectBindSchedulers": {
            temp = dbSelectProjectBindSchedulers(data);
            break;
          }

          case "invoke:dbDeleteProject": {
            temp = dbDeleteProject(data);
            break;
          }

          /* Task Scheduler */

          case "invoke:dbSelectSchedulerList": {
            temp = dbSelectSchedulerList();
            break;
          }

          case "invoke:dbSelectSchedulerDetail": {
            temp = dbSelectSchedulerDetail(data);
            break;
          }

          case "invoke:dbInsertSchedulerDetail": {
            temp = dbInsertSchedulerDetail(data);
            break;
          }

          case "invoke:dbUpdateSchedulerDetail": {
            temp = dbUpdateSchedulerDetail(data);
            break;
          }

          case "invoke:dbDeleteScheduler": {
            temp = dbDeleteScheduler(data);
            break;
          }

          /* Task History */

          case "invoke:dbSelectLimitHistoryList": {
            temp = dbSelectLimitHistoryList(data);
            break;
          }

          case "invoke:dbSelectCountHistoryRunning": {
            temp = dbSelectCountHistoryRunning();
            break;
          }

          case "invoke:fileOpenFolder": {
            temp = await fileOpenFolder(data);
            break;
          }

          case "invoke:dbSelectProjectNewestVersionDetail": {
            temp = dbSelectProjectNewestVersionDetail(data);
            break;
          }

          case "invoke:pythonCancel": {
            temp = pythonCancel(data, webContentsObj);
            break;
          }

          /* Setting */

          case "invoke:select-project-log-folder-path": {
            temp = await selectProjectLogFolder();
            break;
          }

          case "invoke:logCleanFolderByTimeout": {
            temp = logCleanFolderByTimeout(data);
            break;
          }

          case "invoke:logCleanVideoByTimeout": {
            temp = logCleanVideoByTimeout(data);
            break;
          }

          case "invoke:logCleanVideoBySize": {
            temp = logCleanVideoBySize(data);
            break;
          }

          default:
            throw new Error(`An unidentified command in invoke-from-renderer: ${command}.`);
        }

        return { success: true, data: temp };
      } catch (e) {
        loggerMain.error(`Error running command: ${command}`, e);
        return { success: false, data: (e as Error).message ? (e as Error).message : e };
      }
    }
  );

  createWindow();

  app.on("activate", function () {
    // On macOS it's common to re-create a window in the app when the dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Quit when all windows are closed, except on macOS. There, it's common for applications and their menu bar to stay active until the user quits explicitly with Cmd + Q.
app.on("window-all-closed", () => {
  loggerMain.info("Executor window closed.");
  if (process.platform !== "darwin") {
    app.quit();
  }
});

function openProjectLogFolderPath(path: string): void {
  shell.openPath(path).catch((error) => {
    loggerMain.log("error", `Error opening log file: ${path}` + error);
  });
}
