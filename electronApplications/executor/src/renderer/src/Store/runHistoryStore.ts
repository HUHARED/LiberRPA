// FileName: runHistoryStore.ts

import { defineStore } from "pinia";

import { cloneJsonSerializable } from "../Common/json";
import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  RunSource,
  RunStatus,
  RunHistoryItem,
  RunHistoryQueryOptions,
  RunDetails,
} from "../../../shared/run";

export const useRunHistoryStore = defineStore("runHistory", {
  state: () => {
    return {
      arrListItem: [] as RunHistoryItem[],
      totalCount: 0 as number,
      dictOptionsCache: undefined as RunHistoryQueryOptions | undefined,
      intLoadRevision: 0 as number,

      selectedRunId: undefined as number | undefined,
      runDetails: undefined as RunDetails | undefined,
      intDetailsLoadRevision: 0 as number,

      filterScheduleName: "" as string,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as RunStatus | null,
      filterSource: null as RunSource | null,
    };
  },
  actions: {
    async loadRunHistoryPage(optionsDict: RunHistoryQueryOptions | null): Promise<void> {
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

      const intRevision = ++this.intLoadRevision;
      try {
        const result = await invokeMain("getRunHistoryPage", this.dictOptionsCache);
        if (intRevision !== this.intLoadRevision) {
          return;
        }

        this.arrListItem = result.rows;
        this.totalCount = result.total;
      } catch (e: unknown) {
        if (intRevision !== this.intLoadRevision) {
          return;
        }
        throw e;
      }
    },

    async loadRunDetails(historyId: number): Promise<void> {
      if (this.selectedRunId !== historyId) {
        this.selectedRunId = historyId;
        this.runDetails = undefined;
      }

      const intRevision = ++this.intDetailsLoadRevision;
      try {
        const details = await invokeMain("getRunDetails", historyId);
        if (intRevision !== this.intDetailsLoadRevision) return;

        this.runDetails = details;
      } catch (e: unknown) {
        if (intRevision !== this.intDetailsLoadRevision) return;
        throw e;
      }
    },

    closeRunDetails(): void {
      this.intDetailsLoadRevision += 1;
      this.selectedRunId = undefined;
      this.runDetails = undefined;
    },

    async refreshRunHistory(historyId: number): Promise<void> {
      const arrRefresh = [this.loadRunHistoryPage(null)];
      if (this.selectedRunId === historyId) {
        arrRefresh.push(this.loadRunDetails(historyId));
      }
      await Promise.all(arrRefresh);
    },
  },
});
