// FileName: informationStore.ts

import { defineStore } from "pinia";

import { loggerRenderer } from "../Logging/logger";

type ExecutorTab =
  | "packages"
  | "schedules"
  | "jobQueue"
  | "runHistory"
  | "settings"
  | "console";

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "" as string,
      showAlert: false,
      alertRevision: 0,
      tab: "packages" as ExecutorTab,
    };
  },
  actions: {
    showAlertMessage(message: string): void {
      loggerRenderer.error(message);
      this.information = message;
      this.showAlert = true;
      this.alertRevision += 1;
    },
  },
});
