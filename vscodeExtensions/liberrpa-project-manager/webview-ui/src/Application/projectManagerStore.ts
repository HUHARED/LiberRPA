// FileName: projectManagerStore.ts

import { defineStore } from "pinia";

import type {
  Theme,
  ProjectManagerOperation,
} from "../Adapter/Extension/projectManagerMessages";

type AlertType = "info" | "warning" | "error";
type ProjectManagerLoadState = "loading" | "ready" | "failed";

export const useProjectManagerStore = defineStore("projectManager", {
  state: () => ({
    loadState: "loading" as ProjectManagerLoadState,
    busy: false,
    theme: "light" as Theme,
    operation: null as ProjectManagerOperation | null,

    showAlert: false,
    alertType: "info" as AlertType,
    alertMessage: "",
  }),

  actions: {
    load(operation: ProjectManagerOperation, theme: Theme): void {
      this.loadState = "ready";
      this.operation = operation;
      this.theme = theme;
      this.clearAlert();
    },

    showMessage(type: AlertType, message: string): void {
      this.alertType = type;
      this.alertMessage = message;
      this.showAlert = true;
    },

    showError(message: string): void {
      if (this.loadState === "loading") {
        this.loadState = "failed";
      }
      this.showMessage("error", message);
    },

    clearAlert(): void {
      this.showAlert = false;
      this.alertMessage = "";
    },
  },
});
