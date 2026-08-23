import { loggerRenderer } from "../Logging/logger";
import { useRunHistoryStore } from "../Store/runHistoryStore";
import { useRunQueueStore } from "../Store/runQueueStore";
import { useInformationStore } from "../Store/informationStore";
import { useSettingStore } from "../Store/settingStore";

export function registerMainMessageListener(): void {
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
          break;
        }

        case "runEnded": {
          const runHistoryStore = useRunHistoryStore();
          await runHistoryStore.refreshHistoryList();
          break;
        }

        case "runQueueChanged": {
          const runQueueStore = useRunQueueStore();
          runQueueStore.setRunQueue(message.data.items);
          break;
        }
      }
    } catch (e: unknown) {
      const strMessage = e instanceof Error ? e.message : String(e);
      const informationStore = useInformationStore();
      informationStore.showAlertMessage(strMessage);
    }
  });
}
