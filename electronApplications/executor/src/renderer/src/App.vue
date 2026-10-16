<!-- FileName: App.vue -->
<template>
  <v-app class="clean-space fill-height" :theme="settingStore.theme">
    <!-- The Alert area, doesn't join in layout -->
    <Alert />

    <v-main class="clean-space fill-height">
      <v-container class="clean-space fill-height flex-row" fluid>
        <NavigationBar />
        <component :is="componentCurrent" />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { computed } from "vue";
import Alert from "./components/Common/Alert.vue";
import NavigationBar from "./components/Layout/NavigationBar.vue";
import PackagesView from "./components/Projects/PackagesView.vue";
import SchedulesView from "./components/Schedules/SchedulesView.vue";
import JobQueueView from "./components/Runs/JobQueueView.vue";
import RunHistoryView from "./components/Runs/RunHistoryView.vue";
import SettingsView from "./components/Settings/SettingsView.vue";
import ConsoleView from "./components/Console/ConsoleView.vue";
import { loggerRenderer } from "./Logging/logger";
import { useInformationStore } from "./Store/informationStore";
import { useSettingStore } from "./Store/settingStore";

const settingStore = useSettingStore();
const informationStore = useInformationStore();
const componentCurrent = computed(() => {
  loggerRenderer.info(`Switch to tab: ${informationStore.tab}`);
  switch (informationStore.tab) {
    case "projects":
      return PackagesView;
    case "schedules":
      // Schedules refresh their data when opened.
      return SchedulesView;
    case "jobQueue":
      // Job Queue displays the shared scheduling state.
      return JobQueueView;
    case "runHistory":
      // Run History loads its data through the server table.
      return RunHistoryView;
    case "console":
      return ConsoleView;
    default:
      return SettingsView;
  }
});
</script>

<style scoped></style>
