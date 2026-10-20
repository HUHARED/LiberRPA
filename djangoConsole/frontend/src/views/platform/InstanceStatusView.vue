<!-- FileName: InstanceStatusView.vue -->
<template>
  <h1 class="text-h5 mb-4">Instance Status</h1>

  <v-tabs
    :model-value="strActiveTab"
    color="primary"
    class="mb-4"
    aria-label="Instance status sections">
    <v-tab value="overview" :to="{ name: 'platform-instance-status' }">Overview</v-tab>
    <v-tab value="email" :to="{ name: 'platform-email-issues' }">Email</v-tab>
  </v-tabs>

  <RouterView />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

const route = useRoute();
const strActiveTab = computed(() =>
  route.name === "platform-email-issues" ? "email" : "overview",
);
</script>

<style scoped></style>
