<!-- FileName: OrganizationDetailsView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h1 class="text-h5">Organization Details</h1>

    <v-btn
      :to="{ name: 'platform-organizations' }"
      variant="text"
      prepend-icon="mdi-arrow-left">
      Back to Organizations
    </v-btn>
  </div>

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
