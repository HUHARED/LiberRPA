// FileName: index.ts
import { app, dialog, BrowserWindow, ipcMain, nativeImage } from "electron";

function showFatalError(error: unknown): void {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);

  dialog.showErrorBox("UI Analyzer failed to start", message);
}

process.on("uncaughtException", (error: unknown): void => {
  showFatalError(error);
  app.exit(1);
});

process.on("unhandledRejection", (reason: unknown): void => {
  showFatalError(reason);
  app.exit(1);
});

import { join } from "path";
import { electronApp, optimizer, is } from "@electron-toolkit/utils";
import icon from "../../resources/LiberRPA_icon_v3_color_UiAnalyzer_256.ico?asset";
import noLinkIcon from "../../resources/NoLink_16px.png?asset";

import { loggerMain } from "./logger";
import { deleteTimeoutScreenshot } from "./init";
import { dictConfigBasic, strToken } from "./config";
import type { DictInvokeResult, RendererLogLevel } from "../shared/interface";

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
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  webContentsObj = mainWindow.webContents;
  mainWindowObj = mainWindow;

  webContentsObj.on("did-finish-load", () => {
    // NOTE：Delete it before packaging. Open DevTools when the content finishes loading.
    // webContentsObj.openDevTools();

    webContentsObj.send("send-from-main", "init-setting", [dictConfigBasic, strToken]);

    deleteTimeoutScreenshot();
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow.show();
  });

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    loggerMain.info("development mode");
    void mainWindow
      .loadURL(process.env["ELECTRON_RENDERER_URL"])
      .catch((error: unknown) => {
        loggerMain.error("Failed to load renderer URL.", error);
      });
  } else {
    loggerMain.info("production mode");
    void mainWindow
      .loadFile(join(__dirname, "../renderer/index.html"))
      .catch((error: unknown) => {
        loggerMain.error("Failed to load renderer HTML file.", error);
      });
  }
}

function isExpectedSender(
  event: Electron.IpcMainInvokeEvent | Electron.IpcMainEvent
): boolean {
  return event.sender === webContentsObj;
}

function isSocketStatusPayload(data: unknown): data is boolean {
  return typeof data === "boolean";
}

type RendererLogPayload = {
  level: RendererLogLevel;
  message: string;
};

const SET_ALLOWED_LOG_LEVELS = new Set<RendererLogLevel>([
  "error",
  "warn",
  "info",
  "http",
  "verbose",
  "debug",
  "silly",
]);

function isRendererLogPayload(payload: unknown): payload is RendererLogPayload {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }

  const dictPayload = payload as Record<string, unknown>;

  return (
    typeof dictPayload.level === "string" &&
    SET_ALLOWED_LOG_LEVELS.has(dictPayload.level as RendererLogLevel) &&
    typeof dictPayload.message === "string"
  );
}

async function bootstrap(): Promise<void> {
  await app.whenReady();

  electronApp.setAppUserModelId("com.liberrpa.ui-analyzer");

  // Default open or close DevTools by F12 in development and ignore CommandOrControl + R in production.
  app.on("browser-window-created", (_event, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  ipcMain.on("send-from-renderer-log", (event, payload: unknown) => {
    if (!isExpectedSender(event)) {
      return;
    }

    if (!isRendererLogPayload(payload)) {
      return;
    }

    loggerMain.log(payload.level, "[Renderer] " + payload.message);
  });

  ipcMain.handle(
    "invoke-from-renderer",
    async (event, command: string, data?: unknown): Promise<DictInvokeResult> => {
      if (!isExpectedSender(event)) {
        return { success: false, data: "Unexpected IPC sender." };
      }

      loggerMain.debug(
        `[invoke-from-renderer] (${command}) ${JSON.stringify(data, null, 2)}`
      );

      try {
        switch (command) {
          case "cmd-toggle-window":
            if (mainWindowObj.isMinimized()) {
              mainWindowObj.restore();
            } else {
              mainWindowObj.minimize();
            }
            return { success: true };

          case "cmd-toggle-socket-status":
            if (!isSocketStatusPayload(data)) {
              return {
                success: false,
                data: "Invalid payload for cmd-toggle-socket-status.",
              };
            }

            if (data) {
              mainWindowObj.setTitle("UI Analyzer - LiberRPA");
              mainWindowObj.setOverlayIcon(null, "Local Server is working.");
            } else {
              mainWindowObj.setTitle("UI Analyzer - No Local Server");
              mainWindowObj.setOverlayIcon(
                nativeImage.createFromPath(noLinkIcon),
                "No Local Server"
              );
            }
            return { success: true };

          default:
            return {
              success: false,
              data: `Unknown command: ${command}`,
            };
        }
      } catch (e) {
        loggerMain.error(`Error running command: ${command}`, e);
        return { success: false, data: e instanceof Error ? e.message : String(e) };
      }
    }
  );

  createWindow();

  app.on("activate", function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}
void bootstrap().catch((error: unknown) => {
  loggerMain.error("Failed to bootstrap UI Analyzer.", error);
  app.quit();
});

app.on("window-all-closed", () => {
  loggerMain.info("UI Analyzer window closed.");
  app.quit();
});
