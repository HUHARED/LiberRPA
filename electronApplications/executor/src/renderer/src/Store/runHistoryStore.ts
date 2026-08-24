import { defineStore } from "pinia";

import { cloneJsonSerializable } from "../Common/json";
import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  DictRunHistoryItem,
  DictRunHistoryOptions,
  TypeRunHistoryStatus,
} from "../../../shared/run";

export const useRunHistoryStore = defineStore("runHistory", {
  state: () => {
    return {
      arrListItem: [] as DictRunHistoryItem[],
      itemLength: 0 as number,
      dictOptionsCache: undefined as DictRunHistoryOptions | undefined,

      filterScheduleName: "" as string,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as TypeRunHistoryStatus | null,
    };
  },
  actions: {
    async loadRunHistoryPage(options: DictRunHistoryOptions | null): Promise<void> {
      if (options) {
        // Keep an independent copy because v-data-table-server reuses its options object.
        this.dictOptionsCache = cloneJsonSerializable(options);
      }

      // If dictOptionsCache is not undefined, means user has opened Run History, can use the dictOptionsCache to upload data. Otherwise it does not need to refresh.
      if (!this.dictOptionsCache) {
        loggerRenderer.debug(
          "Run History has not been opened, so its data is not refreshed.",
        );
        return;
      }

      const result = await invokeMain(
        "getRunHistoryPage",
        cloneJsonSerializable(this.dictOptionsCache),
      );
      this.arrListItem = result.rows;
      this.itemLength = result.total;
    },

    async refreshRunHistory(): Promise<void> {
      await this.loadRunHistoryPage(null);
    },
  },
});
