import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { Dict_TaskQueue_ListItem } from "../../../shared/interface";

export const useRunQueueStore = defineStore("runQueue", {
  state: () => {
    return {
      arrListItem: [] as Dict_TaskQueue_ListItem[],
    };
  },
  actions: {
    async refreshRunQueue(): Promise<void> {
      this.arrListItem = await invokeMain("selectRunQueue");
    },

    setRunQueue(arrItem: Dict_TaskQueue_ListItem[]): void {
      this.arrListItem = arrItem;
    },

    async cancelWaitingRun(name: string, intEstimatedRunAtMs: number): Promise<void> {
      await invokeMain("cancelWaitingRun", {
        name,
        estimated_run_at_ms: intEstimatedRunAtMs,
      });
      await this.refreshRunQueue();
    },
  },
});
