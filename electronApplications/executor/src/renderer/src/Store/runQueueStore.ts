// FileName: runQueueStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { Dict_ListItem_RunQueue } from "../../../shared/run";

export const useRunQueueStore = defineStore("runQueue", {
  state: () => {
    return {
      arrListItem: [] as Dict_ListItem_RunQueue[],
      intLoadRevision: 0 as number,
    };
  },
  actions: {
    async refreshRunQueue(): Promise<void> {
      const intRevision = ++this.intLoadRevision;
      const arrItem = await invokeMain("getRunQueue");
      if (intRevision === this.intLoadRevision) {
        this.arrListItem = arrItem;
      }
    },

    setRunQueue(arrItem: Dict_ListItem_RunQueue[]): void {
      this.intLoadRevision += 1;
      this.arrListItem = arrItem;
    },

    async cancelWaitingRun(queueId: string): Promise<void> {
      await invokeMain("cancelWaitingRun", queueId);
      await this.refreshRunQueue();
    },
  },
});
