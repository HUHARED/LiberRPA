<!-- FileName: OrganizationSettingsView.vue -->
<template>
  <h1 class="text-h5 mb-4">Organization Settings</h1>
  <v-tabs
    :model-value="strActiveTab"
    color="primary"
    show-arrows
    class="mb-4"
    aria-label="Organization settings sections">
    <v-tab value="general" :to="{ name: 'organization-general' }">General</v-tab>
    <v-tab value="members" :to="{ name: 'members' }">Members</v-tab>
    <v-tab value="departments" :to="{ name: 'departments' }">Departments</v-tab>
    <v-tab value="run-email-recipients" :to="{ name: 'run-email-recipients' }">
      Run Email Recipients
    </v-tab>
    <v-tab value="usage-retention" disabled>Usage &amp; Retention</v-tab>
    <v-tab value="audit-log" :to="{ name: 'audit-log' }">Audit Log</v-tab>
  </v-tabs>
  <RouterView />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

const route = useRoute();
const strActiveTab = computed(() => {
  if (route.name === "members" || route.name === "member-details") return "members";
  if (route.name === "departments" || route.name === "department-details")
    return "departments";
  if (route.name === "run-email-recipients") return "run-email-recipients";
  if (route.name === "audit-log") return "audit-log";
  return "general";
});
</script>

<style scoped></style>
