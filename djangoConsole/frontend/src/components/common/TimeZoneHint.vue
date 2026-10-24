<!-- FileName: TimeZoneHint.vue -->
<template>
  <div
    class="d-flex flex-wrap justify-space-between ga-2 mb-3 text-body-2 text-medium-emphasis">
    <span>Time zone: {{ timeZone }}</span>
    <slot>
      <span v-if="updatedAt">
        Updated at {{ formatDateTime(updatedAt, timeZone, false) }}
      </span>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { formatDateTime } from "@/app/formatters";

defineProps<{ timeZone: string; updatedAt?: string | null }>();
</script>

<style scoped></style>
