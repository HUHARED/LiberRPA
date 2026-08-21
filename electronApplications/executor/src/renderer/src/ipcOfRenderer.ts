// FileName: ipcOfRenderer.ts

import {
  useHistoryStore,
  useInformationStore,
  useQueueStore,
  useSchedulerStore,
  useSettingStore,
} from "./store";
import type { DictExecutorConfig, DictInvokeResult } from "../../shared/interface";

function sendLogToMain(level: string, message: unknown): void {
  console.log(`[${level}] ${String(message)}`);
  window.electron.ipcRenderer.send("send-from-renderer-log", { level, message });
}

export const loggerRenderer = {
  error: (message: unknown): void => sendLogToMain("error", message),
  warn: (message: unknown): void => sendLogToMain("warn", message),
  info: (message: unknown): void => sendLogToMain("info", message),
  http: (message: unknown): void => sendLogToMain("http", message),
  verbose: (message: unknown): void => sendLogToMain("verbose", message),
  debug: (message: unknown): void => sendLogToMain("debug", message),
  silly: (message: unknown): void => sendLogToMain("silly", message),
};

export function sendMain(command: string, data?: unknown): void {
  loggerRenderer.debug("--sendMain--");
  window.electron.ipcRenderer.send("send-from-renderer", command, data);
}

export async function invokeMain<T = unknown>(command: string, data?: unknown): Promise<T> {
  const result = (await window.electron.ipcRenderer.invoke(
    "invoke-from-renderer",
    command,
    data,
  )) as DictInvokeResult;

  if (result.success) {
    return result.data as T;
  }

  const strMessage =
    typeof result.data === "string"
      ? result.data
      : JSON.stringify(result.data ?? "Unknown Main Process error.");
  const informationStore = useInformationStore();
  informationStore.showAlertMessage(strMessage);
  throw new Error(strMessage);
}

let boolIsHandleTaskEnd = false;

window.electron.ipcRenderer.on(
  "send-from-main",
  async (_: Electron.IpcRendererEvent, command: string, data?: unknown) => {
    loggerRenderer.debug(
      `[send-from-main]\ncommand=${command}\ndata=${JSON.stringify(data, null, 2)}`,
    );

    try {
      switch (command) {
        case "init-setting": {
          const settingStore = useSettingStore();
          settingStore.initializeSetting(data as DictExecutorConfig);

          const schedulerStore = useSchedulerStore();
          await schedulerStore.dbSelectSchedulerList();
          break;
        }

        case "pythonResult:taskEnd": {
          if (boolIsHandleTaskEnd) {
            loggerRenderer.warn("A process for 'pythonResult:taskEnd' is running.");
            break;
          }

          boolIsHandleTaskEnd = true;
          try {
            const historyStore = useHistoryStore();
            await historyStore.refreshHistoryList();

            const queueStore = useQueueStore();
            await queueStore.checkWhetherRun_WaitingItem();

            const settingStore = useSettingStore();
            await settingStore.handleDeleteOptions();
          } finally {
            boolIsHandleTaskEnd = false;
          }
          break;
        }

        default:
          throw new Error(
            `An unidentified command in send-from-main: ${command}, data: ${JSON.stringify(
              data,
              null,
              2,
            )}`,
          );
      }
    } catch (e: unknown) {
      const strMessage = e instanceof Error ? e.message : String(e);
      const informationStore = useInformationStore();
      informationStore.showAlertMessage(strMessage);
    }
  },
);
