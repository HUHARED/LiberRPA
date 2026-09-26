<!-- FileName: OrganizationSettingsView.vue -->
<template>
  <h1 class="text-h5 mb-4">Organization Settings</h1>
  <v-tabs
    :model-value="strActiveTab"
    color="primary"
    show-arrows
    class="mb-4"
    aria-label="Organization settings sections">
    <v-tab value="general" disabled>General</v-tab>
    <v-tab value="members" :to="{ name: 'members' }">Members</v-tab>
    <v-tab value="departments" :to="{ name: 'departments' }">Departments</v-tab>
    <v-tab value="run-email-recipients" disabled>Run Email Recipients</v-tab>
    <v-tab value="usage-retention" disabled>Usage &amp; Retention</v-tab>
    <v-tab value="audit-log" disabled>Audit Log</v-tab>
  </v-tabs>
  <RouterView />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

const route = useRoute();
const strActiveTab = computed(() =>
  route.name === "members" || route.name === "member-details" ? "members" : "departments",
);
</script>

<style scoped></style>
