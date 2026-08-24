import { defineStore } from "pinia";

import { loggerRenderer } from "../Logging/logger";

export type TypeExecutorTab =
  | "projects"
  | "schedules"
  | "runQueue"
  | "runHistory"
  | "settings";

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "..." as string,
      showAlert: false,
      alertRevision: 0,
      tab: "projects" as TypeExecutorTab,
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
