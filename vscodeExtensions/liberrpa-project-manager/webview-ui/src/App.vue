<!-- FileName: App.vue -->
<template>
  <v-app class="pa-0 ma-0 fill-height" :theme="projectManagerStore.theme">
    <v-main class="pa-0 ma-0 fill-height overflow-y-auto">
      <Alert style="position: fixed; width: 100%; opacity: 0.9; z-index: 999" />

      <v-container class="pa-4 pa-sm-6" style="min-height: 100vh">
        <CreateProjectView
          v-if="
            projectManagerStore.loadState === 'ready' &&
            projectManagerStore.operation === 'createProject'
          " />
        <PackageProjectView
          v-else-if="
            projectManagerStore.loadState === 'ready' &&
            projectManagerStore.operation === 'packageProject'
          " />
        <PublishComponentView
          v-else-if="
            projectManagerStore.loadState === 'ready' &&
            projectManagerStore.operation === 'publishComponent'
          " />
        <ManageComponentsView
          v-else-if="
            projectManagerStore.loadState === 'ready' &&
            projectManagerStore.operation === 'manageComponents'
          " />
        <div
          v-else-if="projectManagerStore.loadState === 'failed'"
          class="fill-height d-flex flex-column align-center justify-center ga-4 text-center">
          <v-icon icon="mdi-alert-circle-outline" size="48"></v-icon>
          <div>Project Manager could not be loaded.</div>
          <v-btn variant="outlined" @click="showLogs">Show Logs</v-btn>
        </div>
        <div v-else class="fill-height d-flex align-center justify-center">
          <v-progress-circular indeterminate></v-progress-circular>
        </div>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted } from "vue";

import { handleExtensionMessage } from "./Adapter/Extension/projectManagerMessageHandler";
import { postMessage } from "./Adapter/Extension/vscodeApi";
import { useProjectManagerStore } from "./Application/projectManagerStore";
import Alert from "./components/Alert.vue";
import CreateProjectView from "./views/CreateProjectView.vue";
import ManageComponentsView from "./views/ManageComponentsView.vue";
import PackageProjectView from "./views/PackageProjectView.vue";
import PublishComponentView from "./views/PublishComponentView.vue";

const projectManagerStore = useProjectManagerStore();

function showLogs(): void {
  postMessage({ command: "showLogs" });
}

onBeforeMount(() => {
  window.addEventListener("message", handleExtensionMessage);
  postMessage({ command: "ready" });
});

onUnmounted(() => {
  window.removeEventListener("message", handleExtensionMessage);
});
</script>
