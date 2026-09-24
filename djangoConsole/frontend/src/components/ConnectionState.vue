<!-- FileName: ConnectionState.vue -->
<template>
  <v-container class="pa-0 text-center" aria-live="polite">
    <v-progress-circular v-if="loading" indeterminate color="primary" size="40" />
    <v-icon v-else icon="mdi-cloud-alert-outline" size="48" color="primary" />
    <h1 class="text-h5 mt-4 mb-3">
      {{ loading ? "Opening your workspace" : "Unable to connect" }}
    </h1>
    <p class="text-body-2 text-medium-emphasis mb-6">
      {{
        loading
          ? "Checking your session…"
          : (message ?? "The service is temporarily unavailable. Please try again.")
      }}
    </p>
    <v-btn
      v-if="!loading"
      color="primary"
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="retrying"
      @click="$emit('retry')">
      Try Again
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
defineProps<{ loading?: boolean; retrying?: boolean; message?: string }>();
defineEmits<{ retry: [] }>();
</script>

<style scoped></style>
