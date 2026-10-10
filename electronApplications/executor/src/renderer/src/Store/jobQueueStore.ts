// FileName: jobQueueStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import type { JobQueueItem } from "../../../shared/run";

export const useJobQueueStore = defineStore("jobQueue", {
  state: () => {
    return {
      arrListItem: [] as JobQueueItem[],
      intLoadRevision: 0 as number,
    };
  },
  actions: {
    async refreshJobQueue(): Promise<void> {
      const intRevision = ++this.intLoadRevision;
      const arrItem = await invokeMain("getJobQueue");
      if (intRevision === this.intLoadRevision) {
        this.arrListItem = arrItem;
      }
    },

    setJobQueue(arrItem: JobQueueItem[]): void {
      this.intLoadRevision += 1;
      this.arrListItem = arrItem;
    },

    async cancelQueuedRun(queueId: string): Promise<void> {
      await invokeMain("cancelQueuedRun", queueId);
      await this.refreshJobQueue();
    },

    async stopCurrentRun(historyId: number): Promise<void> {
      await invokeMain("pythonCancel", historyId);
      await this.refreshJobQueue();
    },
  },
});
