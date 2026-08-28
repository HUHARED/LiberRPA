// FileName: mainMessage.ts

import { getErrorMessage } from "../../../shared/error";
import { loggerRenderer } from "../Logging/logger";
import { useRunHistoryStore } from "../Store/runHistoryStore";
import { useRunQueueStore } from "../Store/runQueueStore";
import { useInformationStore } from "../Store/informationStore";
import { useSettingStore } from "../Store/settingStore";

export function registerMainMessageListener(): void {
  window.executor.onMainMessage(async (message) => {
    loggerRenderer.debug(`[main-message] ${message.type}`);

    try {
      switch (message.type) {
        case "initializeSetting": {
          const settingStore = useSettingStore();
          settingStore.initializeSetting(
            message.data.configDict,
            message.data.defaultProjectLogFolderPath,
          );
          break;
        }

        case "runEnded": {
          const runHistoryStore = useRunHistoryStore();
          await runHistoryStore.refreshRunHistory();
          break;
        }

        case "runQueueChanged": {
          const runQueueStore = useRunQueueStore();
          runQueueStore.setRunQueue(message.data.items);
          break;
        }
      }
    } catch (e: unknown) {
      const informationStore = useInformationStore();
      informationStore.showAlertMessage(getErrorMessage(e));
    }
  });
}
