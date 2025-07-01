// FileName: ipcOfRenderer.ts

import {
  useSettingStore,
  useInformationStore,
  useHistoryStore,
  useQueueStore,
} from "./store";
import { DictInvokeResult } from "../../shared/interface";

const sendLogToMain = (level: string, message: any): void => {
  // Log to Electron console.
  console.log(`[${level}] ${message}`);
  // Log to local file.
  window.electron.ipcRenderer.send("send-from-renderer-log", { level, message });
};

export const loggerRenderer = {
  error: (message: any): void => sendLogToMain("error", message),
  warn: (message: any): void => sendLogToMain("warn", message),
  info: (message: any): void => sendLogToMain("info", message),
  http: (message: any): void => sendLogToMain("http", message),
  verbose: (message: any): void => sendLogToMain("verbose", message),
  debug: (message: any): void => sendLogToMain("debug", message),
  silly: (message: any): void => sendLogToMain("silly", message),
};

export const sendMain = (command: string, data?: any): void => {
  loggerRenderer.debug("--sendMain--");
  window.electron.ipcRenderer.send("send-from-renderer", command, data);
};

export async function invokeMain(command: string, data?: any): Promise<any> {
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
  } else {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(JSON.stringify(result.data));
  }
}

// Use a flag to "pythonResult:taskEnd"
let boolIsHandleTaskEnd = false;

window.electron.ipcRenderer.on(
  "send-from-main",
  async (_: Electron.IpcRendererEvent, command: string, data?: any) => {
    loggerRenderer.debug(
      `[send-from-main]\ncommand=${command}\ndata=${JSON.stringify(data, null, 2)}`
    );

    switch (command) {
      case "init-setting": {
        const settingStore = useSettingStore();
        settingStore.initializeSetting(data);
        break;
      }

      case "pythonResult:taskEnd": {
        if (boolIsHandleTaskEnd) {
          loggerRenderer.warn("A process for 'pythonResult:taskEnd' is running.");
        } else {
          boolIsHandleTaskEnd = true;
          const historyStore = useHistoryStore();
          await historyStore.refreshHistoryList();

          const queueStore = useQueueStore();
          await queueStore.checkWhetherRun_WaitingItem();

          const settingStore = useSettingStore();
          await settingStore.handleDeleteOptions();
          boolIsHandleTaskEnd = false;
        }

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
