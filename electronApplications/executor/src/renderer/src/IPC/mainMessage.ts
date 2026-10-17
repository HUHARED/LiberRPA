// FileName: mainMessage.ts

import { getErrorMessage } from "../../../shared/error";
import { loggerRenderer } from "../Logging/logger";
import { useConsoleStore } from "../Store/consoleStore";
import { useRunHistoryStore } from "../Store/runHistoryStore";
import { useJobQueueStore } from "../Store/jobQueueStore";
import { useInformationStore } from "../Store/informationStore";
import { useSettingStore } from "../Store/settingStore";

export function registerMainMessageListener(): void {
  window.executor.onMainMessage(async (message) => {
    if (message.type !== "consoleAccountChanged") {
      loggerRenderer.debug(`[main-message] ${message.type}`);
    }

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

        case "consoleAccountChanged": {
          useConsoleStore().setAccount(message.data);
          break;
        }

        case "runEnded": {
          const runHistoryStore = useRunHistoryStore();
          await runHistoryStore.refreshRunHistory();
          break;
        }

        case "jobQueueChanged": {
          const jobQueueStore = useJobQueueStore();
          jobQueueStore.setJobQueue(message.data.items);
          break;
        }
      }
    } catch (e: unknown) {
      const informationStore = useInformationStore();
      informationStore.showAlertMessage(getErrorMessage(e));
    }
  });
}
