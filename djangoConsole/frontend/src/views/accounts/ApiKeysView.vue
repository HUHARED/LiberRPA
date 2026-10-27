<!-- FileName: ApiKeysView.vue -->
<template>
  <h1 class="text-h5 mb-2">API Keys</h1>
  <p class="text-medium-emphasis mb-6">
    API keys can perform Operator actions in the departments your account can currently
    access.
  </p>

  <ApiKeyTable />
</template>

<script setup lang="ts">
import ApiKeyTable from "@/components/accounts/ApiKeyTable.vue";
</script>

<style scoped></style>
