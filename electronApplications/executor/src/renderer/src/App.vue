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
import Alert from "./components/Alert.vue";
import NavigationBar from "./components/NavigationBar.vue";
import Projects from "./components/Projects.vue";
import Schedules from "./components/Schedules.vue";
import RunQueue from "./components/RunQueue.vue";
import RunHistory from "./components/RunHistory.vue";
import Settings from "./components/Settings.vue";
import { loggerRenderer } from "./Logging/logger";
import { useInformationStore } from "./Store/informationStore";
import { useSettingStore } from "./Store/settingStore";

const settingStore = useSettingStore();
const informationStore = useInformationStore();
const componentCurrent = computed(() => {
  loggerRenderer.info(`Switch to tab: ${informationStore.tab}`);
  switch (informationStore.tab) {
    case "projects":
      return Projects;
    case "schedules":
      // Schedules refresh their data when opened.
      return Schedules;
    case "runQueue":
      // Run Queue displays the shared scheduling state.
      return RunQueue;
    case "runHistory":
      // Run History loads its data through the server table.
      return RunHistory;
    default:
      return Settings;
  }
});
</script>

<style scoped></style>
