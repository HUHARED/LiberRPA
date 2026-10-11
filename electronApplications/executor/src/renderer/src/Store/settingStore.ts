// FileName: settingStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { getSystemTimezone } from "../Common/time";
import type { ExecutorConfig } from "../../../shared/config";

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      theme: "light" as "light" | "dark",
      // theme: "dark",
      keepRdpSession: false as boolean,
      keepRdpSessionWidth: 1920 as number,
      keepRdpSessionHeight: 1080 as number,

      logRetentionEnabled: false as boolean,
      logRetentionDays: 7 as number,
      videoRetentionEnabled: false as boolean,
      videoRetentionDays: 7 as number,
      videoStorageLimitEnabled: false as boolean,
      videoStorageLimitGiB: 10 as number,

      projectLogFolderPath: "" as string,
      defaultProjectLogFolderPath: "" as string,

      timezone: getSystemTimezone(),
    };
  },
  actions: {
    initializeSetting(
      configExecutorDict: ExecutorConfig,
      defaultProjectLogFolderPath: string,
    ): void {
      this.theme = configExecutorDict.theme;
      this.keepRdpSession = configExecutorDict.keepRdpSession;
      this.keepRdpSessionWidth = configExecutorDict.keepRdpSessionWidth;
      this.keepRdpSessionHeight = configExecutorDict.keepRdpSessionHeight;
      this.logRetentionEnabled = configExecutorDict.logRetentionEnabled;
      this.logRetentionDays = configExecutorDict.logRetentionDays;
      this.videoRetentionEnabled = configExecutorDict.videoRetentionEnabled;
      this.videoRetentionDays = configExecutorDict.videoRetentionDays;
      this.videoStorageLimitEnabled = configExecutorDict.videoStorageLimitEnabled;
      this.videoStorageLimitGiB = configExecutorDict.videoStorageLimitGiB;
      this.projectLogFolderPath = configExecutorDict.projectLogFolderPath;
      this.defaultProjectLogFolderPath = defaultProjectLogFolderPath;
      this.timezone = configExecutorDict.timezone;
    },

    async selectNewProjectLogFolderPath(): Promise<void> {
      const result = await invokeMain("chooseProjectLogFolder");
      if (result !== null) {
        this.projectLogFolderPath = result;
      }
    },

    useDefaultProjectLogFolderPath(): void {
      this.projectLogFolderPath = "";
    },
  },
});
