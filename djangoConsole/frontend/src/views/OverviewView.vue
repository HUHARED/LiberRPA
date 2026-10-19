<!-- FileName: OverviewView.vue -->
<template>
  <h1 class="text-h5 mb-4">Overview</h1>
  <v-tabs
    :model-value="strActiveTab"
    color="primary"
    show-arrows
    class="mb-4"
    aria-label="Overview sections">
    <v-tab value="current" :to="{ name: 'overview' }">Current Status</v-tab>
    <v-tab value="analysis" :to="{ name: 'overview-analysis' }">Run Analysis</v-tab>
  </v-tabs>

  <RouterView v-slot="{ Component }">
    <KeepAlive include="CurrentRunsView">
      <component :is="Component" />
    </KeepAlive>
  </RouterView>

  <DepartmentAccess />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import DepartmentAccess from "@/components/organizations/DepartmentAccess.vue";

const route = useRoute();
const strActiveTab = computed(() =>
  route.name === "overview-analysis" ? "analysis" : "current",
);
</script>

<style scoped></style>
