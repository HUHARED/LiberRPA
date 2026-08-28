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

    async cancelWaitingRun(queueId: string): Promise<void> {
      await invokeMain("cancelWaitingRun", queueId);
      await this.refreshRunQueue();
    },
  },
});
