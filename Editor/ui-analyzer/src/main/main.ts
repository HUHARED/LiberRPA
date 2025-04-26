// FileName: main.ts
import { loggerMain, openLogPath, strLogPath } from "./logger.js";

loggerMain.info("Start!");

import { app, BrowserWindow, ipcMain } from "electron";
import path from "path";
import { fileURLToPath } from "url";

import { intLocalServerPort, strTheme, boolMinimizeWindow } from "./initLiberRPA.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
loggerMain.debug(`__dirname= ${__dirname}`);
const iconPath = path.join(
  __dirname,
  "../../assets/LiberRPA_icon_v3_color_UiAnalyzer_256.ico"
);
loggerMain.debug(`iconPath= ${iconPath}`);

let main: BrowserWindow;
let viteServer: any = null;

async function createWindow() {
  loggerMain.debug("--createWindow--");

  const mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: true,
    },
    icon: iconPath,
  });

  if (!app.isPackaged) {
    loggerMain.info("development mode");
    // Dynamically import only in dev
    const { startViteServer } = await import("./startViteServer.js");
    const { url, server } = await startViteServer();
    viteServer = server;
    mainWindow.loadURL(url);
    mainWindow.on("closed", () => {
      // Stop the Vite server when the Electron window is closed
      if (server) {
        loggerMain.info("UiAnalyzer server closed.");
        server.close();
      }
    });
  } else {
    loggerMain.info("production mode");
    mainWindow.loadFile(path.join(__dirname, "../index.html"));
  }

  main = mainWindow;
  setTimeout(() => {
    console.log("strLogPath", strLogPath);
    main.webContents.send("log-file-path", strLogPath);
    main.webContents.send("give-localServerPort", intLocalServerPort);
    main.webContents.send("give-theme", strTheme);
    main.webContents.send("give-minimizeWindow", boolMinimizeWindow);
  }, 3000);
}

process.on("uncaughtException", (error) => {
  loggerMain.error(`Uncaught Exception: ${error}`);
  if (viteServer) viteServer.close();
  app.quit();
});
process.on("unhandledRejection", (reason, promise) => {
  loggerMain.error(`Unhandled Rejection at: ${promise}, reason: ${reason}`);
  if (viteServer) viteServer.close();
  app.quit();
});

app
  .whenReady()
  .then(createWindow)
  .catch((error) => {
    loggerMain.error(error);
    app.quit();
  });

app.on("window-all-closed", () => {
  loggerMain.info("UiAnalyzer window closed.");
  if (viteServer) viteServer.close();
  app.quit();
});

ipcMain.on("ipc-from-renderer-log", (_, { level, message }) => {
  loggerMain.log(level, message);
});

ipcMain.on("ipc-from-renderer-ask-localServerPort", () => {
  main.webContents.send("give-localServerPort", intLocalServerPort);
});

ipcMain.on(
  "ipc-from-renderer",
  async (event: Electron.IpcMainEvent, command: string, data?: any) => {
    loggerMain.debug(`[ipc-from-renderer] (${command}) ${data}`);
    try {
      switch (command) {
        case "cmd-open-log-path":
          openLogPath();
          break;

        case "cmd-toggle-window":
          if (main.isMinimized()) {
            main.restore();
          } else {
            main.minimize();
          }
          break;

        default:
          loggerMain.error(
            `An unidentified command in ipc-from-renderer: ${command}, data: ${data}`
          );
          break;
      }
    } catch (err) {
      console.log("typeof err", typeof err);

      if (err instanceof Error) {
        loggerMain.error(`Error running command: ${command}`, err);
        event.sender.send("ipc-from-main", "cmd-error-from-electron", err.message);
      } else if (typeof err === "string") {
        loggerMain.error(`Error running command: ${command}`, err);
        event.sender.send("ipc-from-main", "cmd-error-from-electron", err);
      } else {
        // If it's not an Error instance, handle accordingly.
        loggerMain.error(`An unexpected error occurred: ${command}`);
        event.sender.send(
          "ipc-from-main",
          "cmd-error-from-electron",
          "An unexpected error occurred."
        );
      }
    }
  }
);
