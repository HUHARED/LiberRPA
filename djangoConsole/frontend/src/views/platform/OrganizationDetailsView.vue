<!-- FileName: OrganizationDetailsView.vue -->
<template>
  <v-btn
    :to="{ name: 'platform-organizations' }"
    variant="tonal"
    prepend-icon="mdi-arrow-left"
    class="mb-4">
    Back to Organizations
  </v-btn>

  <h1 class="text-h5 mb-4">Organization Details</h1>

  <v-tabs
    :model-value="route.name"
    color="primary"
    class="mb-4"
    aria-label="Organization details sections">
    <v-tab
      value="platform-organization-details"
      :to="{
        name: 'platform-organization-details',
        params: { organizationId: props.organizationId },
      }">
      Overview
    </v-tab>
    <v-tab
      value="platform-organization-limits"
      :to="{
        name: 'platform-organization-limits',
        params: { organizationId: props.organizationId },
      }">
      Usage &amp; Limits
    </v-tab>
    <v-tab
      value="platform-organization-audit"
      :to="{
        name: 'platform-organization-audit',
        params: { organizationId: props.organizationId },
      }">
      Audit Log
    </v-tab>
  </v-tabs>

  <RouterView v-slot="{ Component }">
    <component :is="Component" :key="props.organizationId" />
  </RouterView>
</template>

<script setup lang="ts">
import { RouterView, useRoute } from "vue-router";

const props = defineProps<{ organizationId: string }>();
const route = useRoute();
</script>

<style scoped></style>
