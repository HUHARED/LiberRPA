// FileName: ipcOfRenderer.ts

import {
  useHistoryStore,
  useInformationStore,
  useQueueStore,
  useSchedulerStore,
  useSettingStore,
} from "./store";
import type {
  TypeExecutorInvokeCommand,
  TypeExecutorInvokeRequest,
  TypeExecutorInvokeResponse,
  TypeIpcArgs,
  TypeRendererLogLevel,
} from "../../shared/ipc";

function sendLogToMain(level: TypeRendererLogLevel, message: unknown): void {
  const strMessage = String(message);
  console.log(`[${level}] ${strMessage}`);
  window.executor.sendLog(level, strMessage);
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

export async function invokeMain<C extends TypeExecutorInvokeCommand>(
  command: C,
  ...args: TypeIpcArgs<TypeExecutorInvokeRequest<C>>
): Promise<TypeExecutorInvokeResponse<C>> {
  const result = await window.executor.invoke(command, ...args);

  if (result.success === false) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(result.error);
    throw new Error(result.error);
  }

  return result.data;
}

let boolIsHandleTaskEnd = false;

window.executor.onMainMessage(async (message) => {
  loggerRenderer.debug(`[main-message]\n${JSON.stringify(message, null, 2)}`);

  try {
    switch (message.type) {
      case "initializeSetting": {
        const settingStore = useSettingStore();
        settingStore.initializeSetting(
          message.data.config,
          message.data.defaultProjectLogFolderPath,
        );

        const schedulerStore = useSchedulerStore();
        await schedulerStore.dbSelectSchedulerList();
        break;
      }

      case "pythonTaskEnded": {
        if (boolIsHandleTaskEnd) {
          loggerRenderer.warn("A Python task-end message is already being handled.");
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
    }
  } catch (e: unknown) {
    const strMessage = e instanceof Error ? e.message : String(e);
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(strMessage);
  }
});
