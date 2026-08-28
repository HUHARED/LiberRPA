// FileName: informationStore.ts

import { defineStore } from "pinia";

import { loggerRenderer } from "../Logging/logger";

type Str_ExecutorTab = "projects" | "schedules" | "runQueue" | "runHistory" | "settings";

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "" as string,
      showAlert: false,
      alertRevision: 0,
      tab: "projects" as Str_ExecutorTab,
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
