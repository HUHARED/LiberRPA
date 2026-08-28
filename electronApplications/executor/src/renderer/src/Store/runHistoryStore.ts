// FileName: runHistoryStore.ts

import { defineStore } from "pinia";

import { cloneJsonSerializable } from "../Common/json";
import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  Dict_RunHistory_Item,
  Dict_RunHistory_Options,
  Str_RunHistory_Status,
} from "../../../shared/run";

export const useRunHistoryStore = defineStore("runHistory", {
  state: () => {
    return {
      arrListItem: [] as Dict_RunHistory_Item[],
      itemLength: 0 as number,
      dictOptionsCache: undefined as Dict_RunHistory_Options | undefined,

      filterScheduleName: "" as string,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as Str_RunHistory_Status | null,
    };
  },
  actions: {
    async loadRunHistoryPage(optionsDict: Dict_RunHistory_Options | null): Promise<void> {
      if (optionsDict) {
        // Keep an independent copy because v-data-table-server reuses its options object.
        this.dictOptionsCache = cloneJsonSerializable(optionsDict);
      }

      // Refresh only after Run History has been opened and table options are available.
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
