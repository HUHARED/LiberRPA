// FileName: ipcOfRenderer.ts
import io from "socket.io-client";

import { useSettingStore, useInformationStore, useSelectorStore } from "./store";
import { removePrefix } from "./attrHandleFunc";
import { DictInvokeResult, DictEleTreeItem, DictBasicConfig } from "../../shared/interface";

const sendLogToMain = (level: string, message: unknown): void => {
  // Log to Electron console.
  console.log(`[${level}] ${message}`);
  // Log to local file.
  window.electron.ipcRenderer.send("send-from-renderer-log", { level, message });
};

export const loggerRenderer = {
  error: (message: unknown): void => sendLogToMain("error", message),
  warn: (message: unknown): void => sendLogToMain("warn", message),
  info: (message: unknown): void => sendLogToMain("info", message),
  http: (message: unknown): void => sendLogToMain("http", message),
  verbose: (message: unknown): void => sendLogToMain("verbose", message),
  debug: (message: unknown): void => sendLogToMain("debug", message),
  silly: (message: unknown): void => sendLogToMain("silly", message),
};

export async function invokeMain(command: string, data?: unknown): Promise<unknown | void> {
  // loggerRenderer.debug("--invokeMain--");
  const result: DictInvokeResult = await window.electron.ipcRenderer.invoke(
    "invoke-from-renderer",
    command,
    data
  );
  /* loggerRenderer.debug(
    `invokeMain result (${command})=\n${JSON.stringify(result, null, 2)}`
  ); */
  if (result.success) {
    return result.data;
  }

  /* const settingStore = useSettingStore();
  settingStore.toggleWindow(); */

  const informationStore = useInformationStore();
  informationStore.showAlertMessage(JSON.stringify(result.data));
  return undefined;
}

window.electron.ipcRenderer.on(
  "send-from-main",
  async (_: Electron.IpcRendererEvent, command: string, data?: unknown) => {
    // Redact token.
    const dataForLog =
      command === "init-setting" && Array.isArray(data) ? [data[0], "[redacted]"] : data;

    loggerRenderer.debug(
      `[send-from-main]\ncommand=${command}\ndata=${JSON.stringify(dataForLog, null, 2)}`
    );

    switch (command) {
      case "init-setting": {
        const settingStore = useSettingStore();
        settingStore.initializeSetting(data as [DictBasicConfig, string]);
        break;
      }

      default:
        loggerRenderer.error(
          `An unidentified command in send-from-main: ${command}, data: ${JSON.stringify(
            data,
            null,
            2
          )}`
        );
        break;
    }
  }
);

/* Create socket. */
let socket: ReturnType<typeof io> | null = null;

export function connectToServer(port: number, token: string): void {
  const settingStore = useSettingStore();
  if (socket && socket.connected) {
    loggerRenderer.debug("Socket.IO already connected: " + socket.id);
    return;
  }
  socket = io(`http://127.0.0.1:${port}`, {
    transports: ["websocket"],
    auth: {
      clientType: "uiAnalyzer",
      token: token,
    },
  });

  socket.on("connect", () => {
    loggerRenderer.debug("Socket.IO connection established: " + socket?.id);
    settingStore.socketState = true;
    void invokeMain("cmd-toggle-socket-status", true);
  });

  socket.on("disconnect", () => {
    loggerRenderer.debug("Socket.IO connection disconnected");
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
  });

  socket.on("connect_error", (e: Error) => {
    console.error("Socket.IO connection error:", e);
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
  });

  socket.on("message_flask_to_uianalyzer", (data: string) => {
    // settingStore.socketState = true;
    loggerRenderer.debug("--message_flask_to_uianalyzer--");
    // loggerRenderer.debug(data);
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

export function sendCmdToFlask(dictCommand: { [key: string]: unknown }): void {
  loggerRenderer.debug("--sendCmdToFlask--");
  if (socket) {
    socket.emit("uianalyzer_command", JSON.stringify(dictCommand));
  }
}
