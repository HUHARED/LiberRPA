// FileName: index.ts
import { app, BrowserWindow, ipcMain, screen } from "electron";
import { join } from "path";
import { electronApp, optimizer, is } from "@electron-toolkit/utils";
import icon from "../../resources/LiberRPA_icon_v3_color_UiAnalyzer_256.ico?asset";

import { loggerMain } from "./logger";
import { deleteTimeoutScreenshot } from "./init";
import { dictConfigBasic } from "./config";
import { DictInvokeResult } from "../shared/interface";

let webContentsObj: Electron.WebContents;
let mainWindowObj: Electron.BrowserWindow;

function createWindow(): void {
  loggerMain.debug("--createWindow--");

  const mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    show: false,
    autoHideMenuBar: true,
    icon: icon,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      sandbox: false,
    },
  });

  webContentsObj = mainWindow.webContents;
  mainWindowObj = mainWindow;

  webContentsObj.on("did-finish-load", () => {
    // NOTE：Delete it before packaging. Open DevTools when the content finishes loading.
    // webContentsObj.openDevTools();

    webContentsObj.send("send-from-main", "init-setting", dictConfigBasic);

    deleteTimeoutScreenshot();
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow.show();
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

app.whenReady().then(() => {
  electronApp.setAppUserModelId("com.liberrpa.ui-analyzer");

  const displays = screen.getAllDisplays();
  if (displays.length === 0) {
    loggerMain.info("Have no screen.");
  } else {
    const mainDisplay = displays.find(
      (display) => display.bounds.x === 0 && display.bounds.y === 0
    );
    if (!mainDisplay) {
      throw new Error("Not found main screen.");
    }
  }

  // Default open or close DevTools by F12 in development and ignore CommandOrControl + R in production.
  app.on("browser-window-created", (_event, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  ipcMain.on("send-from-renderer-log", (_event, { level, message }) =>
    loggerMain.log(level, "[Renderer] " + message)
  );

  ipcMain.handle(
    "invoke-from-renderer",
    async (_event, command: string, data?: any): Promise<DictInvokeResult> => {
      loggerMain.debug(
        `[invoke-from-renderer] (${command}) ${JSON.stringify(data, null, 2)}`
      );
      try {
        let temp: any;
        switch (command) {
          case "cmd-toggle-window":
            if (mainWindowObj.isMinimized()) {
              mainWindowObj.restore();
            } else {
              mainWindowObj.minimize();
            }
            break;

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
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  loggerMain.info("UI Analyzer window closed.");
  app.quit();
});
