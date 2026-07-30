<!-- FileName: App.vue -->
<template>
  <v-app class="pa-0 ma-0 fill-height" :theme="projectManagerStore.theme">
    <v-main class="pa-0 ma-0 fill-height overflow-y-auto">
      <Alert style="position: fixed; width: 100%; opacity: 0.9; z-index: 999" />

      <v-container class="pa-4 pa-sm-6" style="min-height: 100vh">
        <CreateProjectView
          v-if="
            projectManagerStore.loaded && projectManagerStore.operation === 'createProject'
          " />
        <ManageComponentsView
          v-else-if="
            projectManagerStore.loaded &&
            projectManagerStore.operation === 'manageComponents'
          " />
        <div v-else class="fill-height d-flex align-center justify-center">
          <v-progress-circular indeterminate></v-progress-circular>
        </div>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted } from "vue";

import Alert from "./components/Alert.vue";
import CreateProjectView from "./components/CreateProjectView.vue";
import ManageComponentsView from "./components/ManageComponentsView.vue";
import { isMessage_ExtensionToWebview } from "./extensionMessages";
import { useProjectManagerStore } from "./store";
import { postMessage } from "./vscodeApi";

const projectManagerStore = useProjectManagerStore();

function handleMessage(event: MessageEvent): void {
  const message: unknown = event.data;
  if (!isMessage_ExtensionToWebview(message)) {
    console.warn("Ignored invalid extension message:", message);
    return;
  }

  switch (message.command) {
    case "loadCreateProject":
      projectManagerStore.loadCreateProject(message.initialData);
      break;

    case "loadManageComponents":
      projectManagerStore.loadManageComponents(message.initialData);
      break;

    case "projectDependencyPlanBuilt":
      projectManagerStore.setDependencyPlan(
        message.dependencyOperation,
        message.plan,
        message.warningMessages,
      );
      break;

    case "targetFolderSelected":
      projectManagerStore.targetFolder = message.path;
      break;

    case "setBusy":
      projectManagerStore.busy = message.busy;
      break;

    case "componentManagementError":
      if (message.code === "dependency_plan_changed") {
        projectManagerStore.clearDependencyPlan();
      }
      projectManagerStore.showMessage("error", message.message);
      break;

    case "error":
      projectManagerStore.showMessage("error", message.message);
      break;

    case "themeChanged":
      projectManagerStore.theme = message.theme;
      break;
  }
}

onBeforeMount(() => {
  window.addEventListener("message", handleMessage);
  postMessage({ command: "ready" });
});

onUnmounted(() => {
  window.removeEventListener("message", handleMessage);
});
</script>
