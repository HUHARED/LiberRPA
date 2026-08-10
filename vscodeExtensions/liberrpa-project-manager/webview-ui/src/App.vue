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
        <PublishComponentView
          v-else-if="
            projectManagerStore.loaded &&
            projectManagerStore.operation === 'publishComponent'
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

import { handleExtensionMessage } from "./Adapter/Extension/projectManagerMessageHandler";
import { postMessage } from "./Adapter/Extension/vscodeApi";
import { useProjectManagerStore } from "./Application/projectManagerStore";
import Alert from "./components/Alert.vue";
import CreateProjectView from "./views/CreateProjectView.vue";
import ManageComponentsView from "./views/ManageComponentsView.vue";
import PublishComponentView from "./views/PublishComponentView.vue";

const projectManagerStore = useProjectManagerStore();

onBeforeMount(() => {
  window.addEventListener("message", handleExtensionMessage);
  postMessage({ command: "ready" });
});

onUnmounted(() => {
  window.removeEventListener("message", handleExtensionMessage);
});
</script>
