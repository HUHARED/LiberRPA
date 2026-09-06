// FileName: application.ts

import fs from "fs";
import { app, BrowserWindow, ipcMain, nativeImage } from "electron";
import moment from "moment";
import { join } from "path";
import { electronApp, optimizer, is } from "@electron-toolkit/utils";
import type { Logger } from "winston";

import icon from "../../resources/LiberRPA_icon_v3_color_UiAnalyzer_256.ico?asset";
import noLinkIcon from "../../resources/NoLink_16px.png?asset";

import { loadUiAnalyzerMainConfig } from "./config";
import { deleteExpiredScreenshots } from "./init";
import { createMainLogger } from "./logger";
import { getErrorDetails, getErrorMessage } from "../shared/error";
import type {
  DictInvokeResult,
  RendererLogLevel,
  UiAnalyzerInitialization,
} from "../shared/interface";

let mainWindowObj: BrowserWindow | null = null;

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

function getUiAnalyzerInstanceId(): string {
  return `${moment().format("YYYY-MM-DD_HHmmss_SSS")}_${String(process.pid)}`;
}

function configureInstancePaths(
  strDocumentsFolderPath: string,
  strInstanceId: string,
): string {
  const strUserDataFolderPath = join(
    strDocumentsFolderPath,
    "LiberRPA",
    "AppData",
    "ui-analyzer",
  );
  const strSessionDataFolderPath = join(
    app.getPath("temp"),
    "LiberRPA",
    "ui-analyzer",
    "SessionData",
    strInstanceId,
  );

  fs.mkdirSync(strUserDataFolderPath, { recursive: true });
  fs.mkdirSync(strSessionDataFolderPath, { recursive: true });
  app.setPath("userData", strUserDataFolderPath);
  app.setPath("sessionData", strSessionDataFolderPath);

  return strSessionDataFolderPath;
}

function isExpectedSender(
  event: Electron.IpcMainInvokeEvent | Electron.IpcMainEvent,
): boolean {
  return (
    mainWindowObj !== null &&
    !mainWindowObj.isDestroyed() &&
    event.sender === mainWindowObj.webContents
  );
}

function isSocketStatusPayload(data: unknown): data is boolean {
  return typeof data === "boolean";
}

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

function getMainWindow(): BrowserWindow {
  if (mainWindowObj === null || mainWindowObj.isDestroyed()) {
    throw new Error("UI Analyzer window is not available.");
  }

  return mainWindowObj;
}

function registerIpc(loggerMain: Logger): void {
  ipcMain.on("send-from-renderer-log", (event, payload: unknown) => {
    if (!isExpectedSender(event) || !isRendererLogPayload(payload)) {
      return;
    }

    loggerMain.log(payload.level, "[Renderer] " + payload.message);
  });

  ipcMain.handle(
    "invoke-from-renderer",
    async (event, command: unknown, data?: unknown): Promise<DictInvokeResult> => {
      if (!isExpectedSender(event)) {
        return { success: false, data: "Unexpected IPC sender." };
      }

      if (typeof command !== "string") {
        return { success: false, data: "IPC command must be a string." };
      }

      loggerMain.debug(`[invoke-from-renderer] command=${command}`);

      try {
        const mainWindow = getMainWindow();

        switch (command) {
          case "cmd-minimize-window":
            if (!mainWindow.isMinimized()) {
              mainWindow.minimize();
            }
            return { success: true };

          case "cmd-restore-window":
            if (mainWindow.isMinimized()) {
              mainWindow.restore();
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
              mainWindow.setTitle("UI Analyzer - LiberRPA");
              mainWindow.setOverlayIcon(null, "Local Server is working.");
            } else {
              mainWindow.setTitle("UI Analyzer - No Local Server");
              mainWindow.setOverlayIcon(
                nativeImage.createFromPath(noLinkIcon),
                "No Local Server",
              );
            }
            return { success: true };

          default:
            return {
              success: false,
              data: `Unknown command: ${command}`,
            };
        }
      } catch (e: unknown) {
        loggerMain.error(
          `Failed to run Main IPC command ${command}: ${getErrorDetails(e)}`,
        );
        return { success: false, data: getErrorMessage(e) };
      }
    },
  );
}

async function createWindow(
  initialization: UiAnalyzerInitialization,
  loggerMain: Logger,
): Promise<void> {
  loggerMain.debug("--createWindow--");

  const mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    show: false,
    autoHideMenuBar: true,
    icon,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });
  mainWindowObj = mainWindow;

  const webContentsObj = mainWindow.webContents;
  webContentsObj.on("did-finish-load", () => {
    // NOTE: Delete it before packaging. Open DevTools when the content finishes loading.
    // webContentsObj.openDevTools();

    webContentsObj.send("send-from-main", "init-setting", initialization);
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow.show();
  });
  mainWindow.on("closed", () => {
    if (mainWindowObj === mainWindow) {
      mainWindowObj = null;
    }
  });

  try {
    if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
      loggerMain.info("development mode");
      await mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
    } else {
      loggerMain.info("production mode");
      await mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
    }
  } catch (e: unknown) {
    throw new Error(`Failed to load UI Analyzer Renderer: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

export async function bootstrapUiAnalyzer(): Promise<void> {
  let loggerMain: Logger | undefined;

  try {
    const strDocumentsFolderPath = app.getPath("documents");
    const strInstanceId = getUiAnalyzerInstanceId();
    const strSessionDataFolderPath = configureInstancePaths(
      strDocumentsFolderPath,
      strInstanceId,
    );

    const dictConfig = loadUiAnalyzerMainConfig(strDocumentsFolderPath);
    loggerMain = createMainLogger(dictConfig.outputLogPath, strInstanceId);
    loggerMain.info(
      `Start UI Analyzer. instanceId=${strInstanceId}, PID=${String(process.pid)}`,
    );
    loggerMain.debug(`Session data path: ${strSessionDataFolderPath}`);

    await app.whenReady();
    electronApp.setAppUserModelId("com.liberrpa.ui-analyzer");

    // Enable F12 DevTools in development and block CommandOrControl+R in production.
    app.on("browser-window-created", (_event, window) => {
      optimizer.watchWindowShortcuts(window);
    });

    registerIpc(loggerMain);

    app.on("window-all-closed", () => {
      loggerMain?.info("UI Analyzer window closed.");
      app.quit();
    });

    await createWindow(dictConfig.initialization, loggerMain);

    void deleteExpiredScreenshots(dictConfig.documentsFolderPath, loggerMain).catch(
      (e: unknown) => {
        loggerMain?.error(`Failed to clean expired screenshots: ${getErrorDetails(e)}`);
      },
    );
  } catch (e: unknown) {
    loggerMain?.error(`Failed to initialize UI Analyzer: ${getErrorDetails(e)}`);
    throw e;
  }
}
