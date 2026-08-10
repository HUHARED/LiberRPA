// FileName: projectManagerStore.ts

import { defineStore } from "pinia";

import type {
  Theme,
  ProjectManagerOperation,
} from "../Adapter/Extension/projectManagerMessages";

type AlertType = "info" | "warning" | "error";

export const useProjectManagerStore = defineStore("projectManager", {
  state: () => ({
    loaded: false,
    busy: false,
    theme: "light" as Theme,
    operation: null as ProjectManagerOperation | null,

    showAlert: false,
    alertType: "info" as AlertType,
    alertMessage: "",
  }),

  actions: {
    load(operation: ProjectManagerOperation, theme: Theme): void {
      this.loaded = true;
      this.operation = operation;
      this.theme = theme;
      this.clearAlert();
    },

    showMessage(type: AlertType, message: string): void {
      this.alertType = type;
      this.alertMessage = message;
      this.showAlert = true;
    },

    clearAlert(): void {
      this.showAlert = false;
      this.alertMessage = "";
    },
  },
});
