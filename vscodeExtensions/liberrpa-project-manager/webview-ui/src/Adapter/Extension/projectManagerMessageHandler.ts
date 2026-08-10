// FileName: projectManagerMessageHandler.ts

import { useComponentManagementStore } from "../../Application/ComponentManagement/componentManagementStore";
import { useCreateProjectStore } from "../../Application/CreateProject/createProjectStore";
import { usePublishComponentStore } from "../../Application/Publish/publishComponentStore";
import { useProjectManagerStore } from "../../Application/projectManagerStore";
import {
  type DictMessage_ExtensionToWebview,
  isMessage_ExtensionToWebview,
} from "./projectManagerMessages";

function applyMessage(message: DictMessage_ExtensionToWebview): void {
  const projectManagerStore = useProjectManagerStore();
  const createProjectStore = useCreateProjectStore();
  const publishComponentStore = usePublishComponentStore();
  const componentManagementStore = useComponentManagementStore();

  switch (message.command) {
    case "loadCreateProject":
      projectManagerStore.load("createProject", message.initialData.theme);
      createProjectStore.load(message.initialData);
      return;

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

    case "targetFolderSelected":
      createProjectStore.targetFolderPath = message.targetFolderPath;
      return;

    case "setBusy":
      projectManagerStore.busy = message.busy;
      return;

    case "componentManagementError":
      if (message.code === "dependency_plan_changed") {
        componentManagementStore.clearDependencyPlan();
      }
      if (Object.keys(message.details).length > 0) {
        console.error("Component Management error details:", message.details);
      }
      projectManagerStore.showMessage("error", message.message);
      return;

    case "error":
      projectManagerStore.showMessage("error", message.message);
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
