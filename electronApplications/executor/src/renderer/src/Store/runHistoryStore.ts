import { defineStore } from "pinia";

import { sanitizeJsonObj } from "../commonFunc";
import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  DictColumns_History_ListItem_DB,
  Dict_History_Options,
  Dict_History_Options_Component,
  Dict_History_Search,
  TypeTaskHistoryStatus,
} from "../../../shared/interface";

export const useRunHistoryStore = defineStore("runHistory", {
  state: () => {
    return {
      arrListItem: [] as DictColumns_History_ListItem_DB[],
      itemLength: 0 as number,
      dictOptionsCache: undefined as Dict_History_Options | undefined,

      filterSchedulerName: "" as string,
      filterSource: null as "local" | "console" | null,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as TypeTaskHistoryStatus | null,
    };
  },
  actions: {
    async dbSelectLimitHistoryList(
      options: Dict_History_Options_Component | null,
    ): Promise<void> {
      if (options) {
        // Make sure this.dictOptionsCache not use a same object(memory address) with v-data-table-server's options. Otherwise the page button may not work.

        const dictTemp: Dict_History_Options_Component = sanitizeJsonObj(options);

        this.dictOptionsCache = {
          page: dictTemp.page,
          itemsPerPage: dictTemp.itemsPerPage,
          sortBy: dictTemp.sortBy,
          // dictTemp.search is a string, deserialize it.
          search: JSON.parse(dictTemp.search) as Dict_History_Search,
        };
      }

      // If dictOptionsCache is not undefined, means user has clicked Task History, can use the dictOptionsCache to upload data. Otherwise didn't need to refresh.
      if (!this.dictOptionsCache) {
        loggerRenderer.debug("Run History never opened, not updated data.");
        return;
      }

      const result = await invokeMain(
        "selectHistoryList",
        sanitizeJsonObj(this.dictOptionsCache),
      );
      // loggerRenderer.debug(JSON.stringify(result, null, 2));
      this.arrListItem = result.rows;
      this.itemLength = result.total;
    },

    async refreshHistoryList(): Promise<void> {
      await this.dbSelectLimitHistoryList(null);
    },
  },
});
