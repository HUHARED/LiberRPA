import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { getSystemTimezone } from "../time";
import type { DictExecutorConfig } from "../../../shared/interface";

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
      dictConfigExecutor: DictExecutorConfig,
      strDefaultProjectLogFolderPath: string,
    ): void {
      this.theme = dictConfigExecutor.theme;
      this.keepRdpSession = dictConfigExecutor.keepRdpSession;
      this.keepRdpSessionWidth = dictConfigExecutor.keepRdpSessionWidth;
      this.keepRdpSessionHeight = dictConfigExecutor.keepRdpSessionHeight;
      this.logTimeoutEnable = dictConfigExecutor.logTimeoutEnable;
      this.logTimeoutDays = dictConfigExecutor.logTimeoutDays;
      this.videoTimeoutEnable = dictConfigExecutor.videoTimeoutEnable;
      this.videoTimeoutDays = dictConfigExecutor.videoTimeoutDays;
      this.videoSizeEnable = dictConfigExecutor.videoSizeEnable;
      this.videoSizeGB = dictConfigExecutor.videoSizeGB;
      this.projectLogFolderPath = dictConfigExecutor.projectLogFolderPath;
      this.defaultProjectLogFolderPath = strDefaultProjectLogFolderPath;
      this.timezone = dictConfigExecutor.timezone;
    },

    async selectNewProjectLogFolderPath(): Promise<void> {
      const result = await invokeMain("selectProjectLogFolder");
      if (result !== null) {
        this.projectLogFolderPath = result;
      }
    },

    useDefaultProjectLogFolderPath(): void {
      this.projectLogFolderPath = "";
    },
  },
});
