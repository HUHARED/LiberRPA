// FileName: settingStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { getSystemTimezone } from "../Common/time";
import type { Dict_ExecutorConfig } from "../../../shared/config";

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      theme: "light" as "light" | "dark",
      // theme: "dark",
      keepRdpSession: false as boolean,
      keepRdpSessionWidth: 1920 as number,
      keepRdpSessionHeight: 1080 as number,

      logTimeoutEnable: false as boolean,
      logTimeoutDays: 7 as number,
      videoTimeoutEnable: false as boolean,
      videoTimeoutDays: 7 as number,
      videoSizeEnable: false as boolean,
      videoSizeGB: 10 as number,

      projectLogFolderPath: "" as string,
      defaultProjectLogFolderPath: "" as string,

      timezone: getSystemTimezone(),
    };
  },
  actions: {
    initializeSetting(
      configExecutorDict: Dict_ExecutorConfig,
      defaultProjectLogFolderPath: string,
    ): void {
      this.theme = configExecutorDict.theme;
      this.keepRdpSession = configExecutorDict.keepRdpSession;
      this.keepRdpSessionWidth = configExecutorDict.keepRdpSessionWidth;
      this.keepRdpSessionHeight = configExecutorDict.keepRdpSessionHeight;
      this.logTimeoutEnable = configExecutorDict.logTimeoutEnable;
      this.logTimeoutDays = configExecutorDict.logTimeoutDays;
      this.videoTimeoutEnable = configExecutorDict.videoTimeoutEnable;
      this.videoTimeoutDays = configExecutorDict.videoTimeoutDays;
      this.videoSizeEnable = configExecutorDict.videoSizeEnable;
      this.videoSizeGB = configExecutorDict.videoSizeGB;
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
