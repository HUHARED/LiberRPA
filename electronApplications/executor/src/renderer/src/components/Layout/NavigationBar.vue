<!-- FileName: NavigationBar.vue -->
<template>
  <v-tabs
    v-model="informationStore.tab"
    bg-color="navigation"
    color="on-navigation"
    :disabled="consoleStore.boolWorking"
    density="compact"
    direction="vertical"
    class="clean-space fill-height"
    style="width: 55px">
    <v-tab value="projects">
      <v-icon size="x-large" icon="mdi-package-variant-closed"></v-icon>
      <v-tooltip activator="parent" location="bottom">Packages</v-tooltip>
    </v-tab>
    <v-tab value="schedules">
      <v-icon size="x-large" icon="mdi-calendar-clock-outline"></v-icon>
      <v-tooltip activator="parent" location="bottom">Schedules</v-tooltip>
    </v-tab>
    <v-tab value="jobQueue">
      <v-icon size="x-large" icon="mdi-queue-first-in-last-out"></v-icon>
      <v-tooltip activator="parent" location="bottom">Job Queue</v-tooltip>
    </v-tab>
    <v-tab value="runHistory">
      <v-icon size="x-large" icon="mdi-clipboard-text-clock-outline"></v-icon>
      <v-tooltip activator="parent" location="bottom">Run History</v-tooltip>
    </v-tab>
    <v-tab value="settings">
      <v-icon size="x-large" icon="mdi-cog-outline"></v-icon>
      <v-tooltip activator="parent" location="bottom">Settings</v-tooltip>
    </v-tab>
    <v-tab value="console">
      <v-icon size="x-large" icon="mdi-cloud-outline"></v-icon>
      <v-tooltip activator="parent" location="bottom">Console</v-tooltip>
    </v-tab>
  </v-tabs>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { useInformationStore } from "../../Store/informationStore";
import { useConsoleStore } from "../../Store/consoleStore";

const informationStore = useInformationStore();
const consoleStore = useConsoleStore();
const boolSelectingExecutor = computed(
  () => consoleStore.account.sessionInfo?.session.selection_required === true,
);
watch(
  boolSelectingExecutor,
  (boolSelecting) => {
    if (boolSelecting) {
      informationStore.tab = "console";
    }
  },
  { immediate: true },
);
</script>

<style scoped></style>
