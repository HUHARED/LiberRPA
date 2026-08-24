import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { DictRunQueueListItem } from "../../../shared/run";

export const useRunQueueStore = defineStore("runQueue", {
  state: () => {
    return {
      arrListItem: [] as DictRunQueueListItem[],
    };
  },
  actions: {
    async refreshRunQueue(): Promise<void> {
      this.arrListItem = await invokeMain("selectRunQueue");
    },

    setRunQueue(arrItem: DictRunQueueListItem[]): void {
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
