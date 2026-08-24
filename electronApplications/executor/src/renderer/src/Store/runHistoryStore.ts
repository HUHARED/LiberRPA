import { defineStore } from "pinia";

import { cloneJsonSerializable } from "../Common/json";
import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  DictColumns_RunHistory_ListItem_DB,
  DictRunHistoryOptions,
  DictRunHistorySearch,
  TypeRunHistoryStatus,
} from "../../../shared/run";

interface DictRunHistoryTableOptions extends Omit<DictRunHistoryOptions, "search"> {
  search: string;
}

export const useRunHistoryStore = defineStore("runHistory", {
  state: () => {
    return {
      arrListItem: [] as DictColumns_RunHistory_ListItem_DB[],
      itemLength: 0 as number,
      dictOptionsCache: undefined as DictRunHistoryOptions | undefined,

      filterScheduleName: "" as string,
      filterSource: null as "local" | "console" | null,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as TypeRunHistoryStatus | null,
    };
  },
  actions: {
    async loadRunHistoryPage(options: DictRunHistoryTableOptions | null): Promise<void> {
      if (options) {
        // Make sure this.dictOptionsCache not use a same object(memory address) with v-data-table-server's options. Otherwise the page button may not work.

        const dictTemp: DictRunHistoryTableOptions = cloneJsonSerializable(options);

        this.dictOptionsCache = {
          page: dictTemp.page,
          itemsPerPage: dictTemp.itemsPerPage,
          sortBy: dictTemp.sortBy,
          // dictTemp.search is a string, deserialize it.
          search: JSON.parse(dictTemp.search) as DictRunHistorySearch,
        };
      }

      // If dictOptionsCache is not undefined, means user has opened Run History, can use the dictOptionsCache to upload data. Otherwise it does not need to refresh.
      if (!this.dictOptionsCache) {
        loggerRenderer.debug(
          "Run History has not been opened, so its data is not refreshed.",
        );
        return;
      }

      const result = await invokeMain(
        "selectRunHistoryPage",
        cloneJsonSerializable(this.dictOptionsCache),
      );
      // loggerRenderer.debug(JSON.stringify(result, null, 2));
      this.arrListItem = result.rows;
      this.itemLength = result.total;
    },

    async refreshRunHistory(): Promise<void> {
      await this.loadRunHistoryPage(null);
    },
  },
});
