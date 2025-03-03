// FileName: ipcOfRenderer.ts
const { ipcRenderer } = require("electron");
// import { ipcRenderer } from "electron"; Cannot use it, it will error.
import { useSettingStore, useInformationStore, useSelectorStore } from "./store";
import { removePrefix } from "./commonFunc";
import { DictEleTreeItem } from "./interface";
import io from "socket.io-client";

export const loggerRenderer = {
  error: (message: any) => sendLogToMain("error", message),
  warn: (message: any) => sendLogToMain("warn", message),
  info: (message: any) => sendLogToMain("info", message),
  http: (message: any) => sendLogToMain("http", message),
  verbose: (message: any) => sendLogToMain("verbose", message),
  debug: (message: any) => sendLogToMain("debug", message),
  silly: (message: any) => sendLogToMain("silly", message),
};

const sendLogToMain = (level: string, message: any) => {
  // Log to Electron console.
  console.log(`[${level}] ${message}`);
  // Log to local file.
  if (window && window.process && window.process.type === "renderer") {
    const { ipcRenderer } = require("electron");
    ipcRenderer.send("ipc-from-renderer-log", { level, message });
  } else {
    console.log("Not running in Electron.");
  }
};

export const sendIpcMessageToMain = (command: string, data?: any) => {
  loggerRenderer.debug("--sendIpcMessageToMain--");

  if (window && window.process && window.process.type === "renderer") {
    const { ipcRenderer } = require("electron");
    ipcRenderer.send("ipc-from-renderer", command, data);
  } else {
    loggerRenderer.debug("Not running in Electron.");
  }
};

ipcRenderer.on("log-file-path", (_: any, strLogPath: string) => {
  loggerRenderer.debug("strLogPath: " + strLogPath);
  // Use Pinia after initializing done.
  const settingStore = useSettingStore();
  settingStore.strLogPath = strLogPath;
});

// Create socket.
let socket: ReturnType<typeof io> | null = null;

function connectToServer(port: number): void {
  const settingStore = useSettingStore();
  if (socket && socket.connected) {
    console.log("Socket.IO already connected: " + socket.id);
    return;
  }
  socket = io(`http://localhost:${port}`, {
    transports: ["websocket"],
  });

  socket.on("connect", () => {
    loggerRenderer.debug("Socket.IO connection established: " + socket?.id);
    settingStore.socketState = true;
  });

  socket.on("disconnect", () => {
    loggerRenderer.debug("Socket.IO connection disconnected");
    settingStore.socketState = false;
  });

  socket.on("connect_error", (e: Error) => {
    console.error("Socket.IO connection error:", e);
    settingStore.socketState = false;
  });

  socket.on("message_flask_to_uianalyzer", async (data: string) => {
    // settingStore.socketState = true;
    loggerRenderer.debug("--message_flask_to_uianalyzer--");
    loggerRenderer.debug(data);
    const selectorStore = useSelectorStore();

    if (data.startsWith("Element_Tree:")) {
      data = removePrefix(data, "Element_Tree:");
      const dictResult: [DictEleTreeItem[], number[], number] = JSON.parse(data);
      selectorStore.arrEleTree = dictResult[0];
      selectorStore.arrEleTreeOpened = dictResult[1];
      selectorStore.intEleTreeActivated = dictResult[2];
      selectorStore.updateEleTreeSelector();
    } else {
      const dictResult = JSON.parse(data);

      const informationStore = useInformationStore();
      informationStore.information = JSON.stringify(dictResult["data"]);
      selectorStore.processDescription = "Idle";
    }
  });
}

export function sendCmdToFlask(dictCommand: { [key: string]: any }): void {
  loggerRenderer.debug("--sendCmdToFlask--");
  if (!socket) {
    ipcRenderer.send("ipc-from-renderer-ask-localServerPort");
  } else {
    socket.emit("uianalyzer_command", JSON.stringify(dictCommand));
  }
}

ipcRenderer.on("give-localServerPort", (_: any, intLocalServerPort: number) => {
  loggerRenderer.debug("intLocalServerPort:" + intLocalServerPort);
  // Use Pinia after initializing done.
  const settingStore = useSettingStore();
  settingStore.intLocalServerPort = intLocalServerPort;

  if (settingStore.intLocalServerPort === undefined) {
    ipcRenderer.send("ipc-from-renderer-ask-localServerPort");
  } else {
    connectToServer(intLocalServerPort);
  }
});

ipcRenderer.on("give-theme", (_: any, strTheme: string) => {
  loggerRenderer.debug("strTheme:" + strTheme);
  const settingStore = useSettingStore();
  settingStore.theme = strTheme;
});

ipcRenderer.on("give-minimizeWindow", (_: any, boolMinimizeWindow: boolean) => {
  loggerRenderer.debug("boolMinimizeWindow:" + boolMinimizeWindow);
  const settingStore = useSettingStore();
  settingStore.minimizeWindow = boolMinimizeWindow;
});

ipcRenderer.on(
  "ipc-from-main",
  (_: Electron.IpcRendererEvent, command: string, data?: any) => {
    loggerRenderer.debug(`(ipc-from-main)\ncommand=${command}\ndata=${data}`);

    const informationStore = useInformationStore();
    const settingStore = useSettingStore();

    switch (command) {
      case "cmd-error-from-electron":
        informationStore.information = data;
        settingStore.toggleWindow();
        break;

      default:
        loggerRenderer.error(
          `An unidentified command in ipc-from-main: ${command}, data: ${data}`
        );
        break;
    }
  }
);
