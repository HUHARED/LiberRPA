// FileName: runQueueStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { RunQueueItem } from "../../../shared/run";

export const useRunQueueStore = defineStore("runQueue", {
  state: () => {
    return {
      arrListItem: [] as RunQueueItem[],
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

    setRunQueue(arrItem: RunQueueItem[]): void {
      this.intLoadRevision += 1;
      this.arrListItem = arrItem;
    },

    async cancelQueuedRun(queueId: string): Promise<void> {
      await invokeMain("cancelQueuedRun", queueId);
      await this.refreshRunQueue();
    },

    async stopCurrentRun(historyId: number): Promise<void> {
      await invokeMain("pythonCancel", historyId);
      await this.refreshRunQueue();
    },
  },
});
