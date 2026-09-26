<!-- FileName: ApiKeysView.vue -->
<template>
  <h1 class="text-h5 mb-2">API Keys</h1>
  <p class="text-medium-emphasis mb-6">
    Keys perform Operator actions within your current account access. Organization
    administrators can access all departments; other members use their explicit department
    roles. A member without department access can create a key but cannot access department
    resources yet.
  </p>
  <ApiKeyTable />
</template>

<script setup lang="ts">
import ApiKeyTable from "../components/ApiKeyTable.vue";
</script>

<style scoped></style>
