// FileName: projectManagerMessageHandler.ts

import { useComponentManagementStore } from "../../Application/ComponentManagement/componentManagementStore";
import { useCreateProjectStore } from "../../Application/CreateProject/createProjectStore";
import { usePackageProjectStore } from "../../Application/PackageProject/packageProjectStore";
import { usePublishComponentStore } from "../../Application/Publish/publishComponentStore";
import { useProjectManagerStore } from "../../Application/projectManagerStore";
import { useConsoleAccountStore } from "../../Application/Console/consoleAccountStore";
import {
  type DictMessage_ExtensionToWebview,
  isMessage_ExtensionToWebview,
} from "./projectManagerMessages";
import { ConsoleAction } from "../../Domain/Console/consoleTypes";

function applyMessage(message: DictMessage_ExtensionToWebview): void {
  const projectManagerStore = useProjectManagerStore();
  const createProjectStore = useCreateProjectStore();
  const packageProjectStore = usePackageProjectStore();
  const publishComponentStore = usePublishComponentStore();
  const componentManagementStore = useComponentManagementStore();

  switch (message.command) {
    // Create Project.
    case "loadCreateProject":
      projectManagerStore.load("createProject", message.initialData.theme);
      createProjectStore.load(message.initialData);
      return;

    case "targetFolderSelected":
      createProjectStore.targetFolderPath = message.targetFolderPath;
      return;

    // Package Project.
    case "loadPackageProject":
      projectManagerStore.load("packageProject", message.initialData.theme);
      packageProjectStore.load(message.initialData);
      if (message.initialData.notification !== undefined) {
        projectManagerStore.showMessage(
          message.initialData.notification.type,
          message.initialData.notification.message,
        );
      }
      return;

    case "consolePublishChanged":
      packageProjectStore.consolePublishResult = message.result;
      return;

    // Publish Component.
    case "loadPublishComponent":
      projectManagerStore.load("publishComponent", message.initialData.theme);
      publishComponentStore.load(message.initialData);
      if (message.initialData.notification !== undefined) {
        projectManagerStore.showMessage(
          message.initialData.notification.type,
          message.initialData.notification.message,
        );
      }
      return;

    // Manage Components.
    case "loadManageComponents":
      projectManagerStore.load("manageComponents", message.initialData.theme);
      componentManagementStore.load(message.initialData);
      if (message.initialData.notification !== undefined) {
        projectManagerStore.showMessage(
          message.initialData.notification.type,
          message.initialData.notification.message,
        );
      }
      return;

    case "projectDependencyPlanBuilt":
      componentManagementStore.setDependencyPlan(
        message.dependencyOperation,
        message.plan,
        message.warningMessages,
      );
      return;

    // Console account.
    case "loadConsole":
      projectManagerStore.load("console", message.theme);
      useConsoleAccountStore().load(message.state);
      return;

    case "consoleStateChanged":
      useConsoleAccountStore().load(message.state);
      return;

    case "consoleActionFinished":
      useConsoleAccountStore().finishAction(message.action, message.error);
      if (
        message.error !== null &&
        message.action !== ConsoleAction.ChangeAddress &&
        message.action !== ConsoleAction.SignIn
      ) {
        projectManagerStore.showError(message.error);
      }
      return;

    // Shared feedback.
    case "setBusy":
      projectManagerStore.busy = message.busy;
      return;

    case "componentManagementError":
      if (message.code === "dependency_plan_changed") {
        componentManagementStore.clearDependencyPlan();
      }
      projectManagerStore.showError(message.message);
      return;

    case "error":
      projectManagerStore.showError(message.message);
      return;

    case "themeChanged":
      projectManagerStore.theme = message.theme;
  }
}

export function handleExtensionMessage(event: MessageEvent): void {
  const value: unknown = event.data;
  if (!isMessage_ExtensionToWebview(value)) {
    console.warn("Ignored invalid Extension message:", value);
    return;
  }

  applyMessage(value);
}
