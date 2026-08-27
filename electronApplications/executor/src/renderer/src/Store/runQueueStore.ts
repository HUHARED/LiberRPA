// FileName: runQueueStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { Dict_ListItem_RunQueue } from "../../../shared/run";

export const useRunQueueStore = defineStore("runQueue", {
  state: () => {
    return {
      arrListItem: [] as Dict_ListItem_RunQueue[],
    };
  },
  actions: {
    async refreshRunQueue(): Promise<void> {
      this.arrListItem = await invokeMain("getRunQueue");
    },

    setRunQueue(arrItem: Dict_ListItem_RunQueue[]): void {
      this.arrListItem = arrItem;
    },

    async cancelWaitingRun(
      scheduleName: string,
      intEstimatedRunAtMs: number,
    ): Promise<void> {
      await invokeMain("cancelWaitingRun", {
        schedule_name: scheduleName,
        estimated_run_at_ms: intEstimatedRunAtMs,
      });
      await this.refreshRunQueue();
    },
  },
});
