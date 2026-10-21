<!-- FileName: OrganizationUsageTable.vue -->
<template>
  <v-alert v-if="warning" type="warning" variant="tonal" class="mb-4" role="status">
    {{ warning }}
  </v-alert>

  <v-card variant="outlined" :aria-busy="loading">
    <v-data-table
      :headers="arrHeader"
      :items="limits"
      :items-per-page="-1"
      :loading="loading"
      :mobile-breakpoint="600"
      item-value="key"
      loading-text="Loading usage and limits…"
      disable-sort
      hide-default-footer>
      <template #item.used="{ item }">
        {{ formatOrganizationLimit(item.used, item.unit) }}
      </template>

      <template #item.reserved="{ item }">
        {{ formatOrganizationLimit(item.reserved, item.unit) }}
      </template>

      <template #item.limit="{ item }">
        {{ formatOrganizationLimit(item.limit, item.unit) }}
      </template>

      <template #item.source="{ item }">
        {{ item.override === null ? "Default" : "Override" }}
      </template>

      <template #item.actions="{ item }">
        <div
          v-if="item.key === OrganizationLimit.MaxStoredBytesPerOrganization"
          class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="'Packages'"
            to="/packages"
            variant="text"
            size="small"
            aria-label="Open Packages"
            icon="mdi-package-variant-closed" />

          <v-btn
            v-tooltip:bottom="'Shared Files'"
            to="/shared-files"
            variant="text"
            size="small"
            aria-label="Open Shared Files"
            icon="mdi-folder-outline" />
        </div>
        <v-btn
          v-else-if="DICT_RESOURCE_ROUTE[item.key]"
          v-tooltip:bottom="`Open ${item.label}`"
          :to="DICT_RESOURCE_ROUTE[item.key]"
          variant="text"
          size="small"
          :aria-label="`Open ${item.label}`"
          icon="mdi-open-in-new" />
      </template>

      <template #no-data>
        {{ error ? "Usage could not be loaded." : "No usage data." }}
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import {
  OrganizationLimit,
  type OrganizationLimitResponse,
} from "@/api/generated/browserApi";

import { formatOrganizationLimit } from "@/app/organizationLimits";

const props = defineProps<{
  limits: OrganizationLimitResponse[];
  loading: boolean;
  error: boolean;
  showActions?: boolean;
  warning?: string | null;
}>();

const DICT_RESOURCE_ROUTE: Partial<Record<OrganizationLimit, string>> = {
  [OrganizationLimit.MaxMembersPerOrganization]: "/organization-settings/members",
  [OrganizationLimit.MaxDepartmentsPerOrganization]: "/organization-settings/departments",
  [OrganizationLimit.MaxExecutorsPerOrganization]: "/executors",
  [OrganizationLimit.MaxExecutorGroupsPerOrganization]: "/executors/groups",
  [OrganizationLimit.MaxProjectsPerOrganization]: "/packages",
  [OrganizationLimit.MaxPackagesPerProject]: "/packages",
  [OrganizationLimit.MaxSchedulesPerOrganization]: "/schedules",
  [OrganizationLimit.MaxAssetsPerOrganization]: "/assets",
  [OrganizationLimit.MaxDataQueuesPerOrganization]: "/data-queues",
  [OrganizationLimit.MaxSharedFilesPerOrganization]: "/shared-files",
  [OrganizationLimit.MaxRunEmailAddressesPerOrganization]:
    "/organization-settings/run-email-recipients",
  [OrganizationLimit.MaxQueueItemsPerOrganization]: "/data-queues",
  [OrganizationLimit.MaxQueueDataBytesPerOrganization]: "/data-queues",
  [OrganizationLimit.MaxRunLogBytesPerOrganization]: "/runs",
  [OrganizationLimit.MaxRunLogGroupsPerOrganization]: "/runs",
  [OrganizationLimit.MaxRunHistoryPerOrganization]: "/runs",
  [OrganizationLimit.MaxActiveJobsPerOrganization]: "/jobs",
};

const arrHeader = computed(() => [
  { title: "Resource", key: "label", minWidth: 240 },
  { title: "Used", key: "used", minWidth: 120 },
  { title: "Reserved", key: "reserved", minWidth: 120 },
  { title: "Limit", key: "limit", minWidth: 120 },
  { title: "Source", key: "source", width: 112 },
  ...(props.showActions ? [{ title: "Actions", key: "actions", width: 112 }] : []),
]);
</script>

<style scoped></style>
