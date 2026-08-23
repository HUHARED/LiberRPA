<!-- FileName: App.vue -->
<template>
  <v-app class="clean-space fill-height" :theme="settingStore.theme">
    <!-- The Alert area, doesn't join in layout -->
    <Alert />

    <v-main class="clean-space fill-height">
      <v-container class="clean-space fill-height flex-row" fluid>
        <TabBar />
        <component :is="componentCurrent" />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { computed } from "vue";
import Alert from "./components/Alert.vue";
import TabBar from "./components/TabBar.vue";
import ProjectLocalPackage from "./components/ProjectLocalPackage.vue";
import TaskScheduler from "./components/TaskScheduler.vue";
import TaskQueue from "./components/TaskQueue.vue";
import TaskHistory from "./components/TaskHistory.vue";
import Setting from "./components/Setting.vue";
import { loggerRenderer } from "./ipcOfRenderer";
import { useInformationStore, useSettingStore } from "./store";

const settingStore = useSettingStore();
const informationStore = useInformationStore();
const componentCurrent = computed(() => {
  loggerRenderer.info(`Switch to tab: ${informationStore.tab}`);
  switch (informationStore.tab) {
    case "Project Local Package":
      return ProjectLocalPackage;
    case "Task Scheduler":
      // Task Scheduler refreshes its data when opened.
      return TaskScheduler;
    case "Task Queue":
      // Task Queue displays the shared scheduling state.
      return TaskQueue;
    case "Task History":
      // Task History loads its data through the server table.
      return TaskHistory;
    default:
      return Setting;
  }
});
</script>

<style scoped></style>
