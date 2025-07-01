<!-- FileName: TabBar.vue -->
<template>
  <v-tabs
    v-model="informationStore.tab"
    bg-color="#205781"
    density="compact"
    direction="vertical"
    class="clean-space fill-height"
    style="width: 55px">
    <v-tab value="Project Local Package">
      <v-icon size="x-large" icon="mdi-format-list-bulleted-square"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Project Local Package </v-tooltip>
    </v-tab>
    <v-tab value="Task Scheduler">
      <v-icon size="x-large" icon="mdi-timer-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Task Scheduler </v-tooltip>
    </v-tab>
    <v-tab value="Task Queue">
      <v-icon size="x-large" icon="mdi-queue-first-in-last-out"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Task Queue </v-tooltip>
    </v-tab>
    <v-tab value="Task History">
      <v-icon size="x-large" icon="mdi-clipboard-text-clock-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Task History </v-tooltip>
    </v-tab>
    <v-tab value="Setting">
      <v-icon size="x-large" icon="mdi-cog-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Setting </v-tooltip>
    </v-tab>
  </v-tabs>
</template>

<script setup lang="ts">
import { useInformationStore } from "../store";

const informationStore = useInformationStore();
</script>

<style scoped></style>
