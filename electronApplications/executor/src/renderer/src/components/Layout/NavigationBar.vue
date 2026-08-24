<template>
  <v-tabs
    v-model="informationStore.tab"
    bg-color="#205781"
    density="compact"
    direction="vertical"
    class="clean-space fill-height"
    style="width: 55px">
    <v-tab value="projects">
      <v-icon size="x-large" icon="mdi-format-list-bulleted-square"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Projects </v-tooltip>
    </v-tab>
    <v-tab value="schedules">
      <v-icon size="x-large" icon="mdi-timer-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Schedules </v-tooltip>
    </v-tab>
    <v-tab value="runQueue">
      <v-icon size="x-large" icon="mdi-queue-first-in-last-out"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Run Queue </v-tooltip>
    </v-tab>
    <v-tab value="runHistory">
      <v-icon size="x-large" icon="mdi-clipboard-text-clock-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Run History </v-tooltip>
    </v-tab>
    <v-tab value="settings">
      <v-icon size="x-large" icon="mdi-cog-outline"> </v-icon>
      <v-tooltip activator="parent" location="bottom"> Settings </v-tooltip>
    </v-tab>
  </v-tabs>
</template>

<script setup lang="ts">
import { useInformationStore } from "../../Store/informationStore";

const informationStore = useInformationStore();
</script>

<style scoped></style>
