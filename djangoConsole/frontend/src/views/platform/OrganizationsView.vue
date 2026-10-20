<!-- FileName: OrganizationsView.vue -->
<template>
  <div class="d-flex align-center justify-space-between ga-4 mb-4">
    <h1 class="text-h5">Organizations</h1>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      @click="loadOrganizations()">
      Refresh
    </v-btn>
  </div>

  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <v-form @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="4">
            <v-text-field v-model="strName" label="Name" variant="outlined" hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="strOrganizationId"
              label="Organization ID"
              variant="outlined"
              placeholder="Full organization ID"
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-select
              v-model="arrStatus"
              :items="ARR_STATUS_OPTION"
              label="Status"
              variant="outlined"
              multiple
              chips
              clearable
              hide-details />
          </v-col>
        </v-row>

        <div class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="resetFilters">Reset</v-btn>
          <v-btn type="submit" color="primary" variant="tonal">Apply</v-btn>
        </div>
      </v-form>
    </v-card-text>
  </v-card>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="organizationPage" class="mt-2">
      Previously loaded organizations are shown and may be out of date.
    </p>
  </v-alert>

  <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
    Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
  </p>

  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="arrHeader"
      :items="organizationPage?.organizations ?? []"
      :items-length="organizationPage?.pagination.total_count ?? 0"
      :items-per-page="organizationPage?.pagination.page_size ?? INT_LIST_PAGE_SIZE"
      :page="organizationPage?.pagination.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading organizations…"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <RouterLink
          :to="{
            name: 'platform-organization-limits',
            params: { organizationId: item.id },
          }"
          class="table-text text-primary text-decoration-none">
          {{ item.name }}
        </RouterLink>
      </template>

      <template #item.administrators="{ item }">
        <template v-if="item.administrators[0]">
          <p class="table-text">
            {{ item.administrators[0].name || item.administrators[0].email }}
          </p>
          <p v-if="item.administrators[0].name" class="text-body-2 text-medium-emphasis">
            {{ item.administrators[0].email }}
          </p>
          <p v-if="item.administrators.length > 1" class="text-body-2 text-medium-emphasis">
            +{{ item.administrators.length - 1 }}
          </p>
        </template>
        <span v-else>—</span>
      </template>

      <template #item.notes="{ item }">
        <div class="table-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>

      <template #item.created_at="{ item }">
        {{ formatDateTime(item.created_at, strTimeZone) }}
      </template>

      <template #item.status="{ item }">
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-if="
              !item.suspended_at && !item.deletion_requested_at && !item.deletion_started_at
            "
            color="success"
            size="small"
            variant="tonal">
            Active
          </v-chip>
          <v-chip v-if="item.suspended_at" color="warning" size="small" variant="tonal">
            Suspended
          </v-chip>
          <v-chip
            v-if="item.deletion_started_at"
            color="error"
            size="small"
            variant="tonal">
            Deletion in Progress
          </v-chip>
          <v-chip
            v-else-if="item.deletion_requested_at"
            color="warning"
            size="small"
            variant="tonal">
            Deletion Scheduled
          </v-chip>
        </div>
      </template>

      <template #item.actions="{ item }">
        <v-btn
          :to="{
            name: 'platform-organization-limits',
            params: { organizationId: item.id },
          }"
          :aria-label="`View ${item.name}`"
          variant="text"
          size="small"
          prepend-icon="mdi-eye-outline">
          View
        </v-btn>
      </template>

      <template #no-data>
        {{
          requestError
            ? "The organization list could not be loaded."
            : "No organizations found."
        }}
      </template>
    </v-data-table-server>

    <template v-if="organizationPage">
      <v-divider />

      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ organizationPage.pagination.total_count }} organizations · Page
          {{ organizationPage.pagination.page }} of
          {{ organizationPage.pagination.total_pages }}
        </p>

        <v-pagination
          v-if="organizationPage.pagination.total_pages > 1"
          :model-value="organizationPage.pagination.page"
          :length="organizationPage.pagination.total_pages"
          :total-visible="5"
          density="comfortable"
          aria-label="Organization pages"
          @update:model-value="loadOrganizations" />
      </div>
    </template>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getPlatformOrganizationList } from "@/api/organizationLimits";
import {
  INT_LIST_PAGE_SIZE,
  PlatformOrganizationStatus,
  type PlatformOrganizationListResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const ARR_STATUS_OPTION = [
  { title: "Active", value: PlatformOrganizationStatus.Active },
  { title: "Suspended", value: PlatformOrganizationStatus.Suspended },
  { title: "Deletion Scheduled", value: PlatformOrganizationStatus.DeletionScheduled },
  { title: "Deletion in Progress", value: PlatformOrganizationStatus.DeletionInProgress },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const strName = ref("");
const strOrganizationId = ref("");
const arrStatus = ref<PlatformOrganizationStatus[]>([]);
let appliedFilters = {
  name: "",
  organizationId: "",
  statuses: [] as PlatformOrganizationStatus[],
};

const organizationPage = shallowRef<PlatformOrganizationListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const strUpdatedAt = ref<string | null>(null);
const boolLoading = ref(false);
let intRequestRevision = 0;
let intRequestedPage = 1;

const arrHeader = computed(() => [
  { title: "Name", key: "name", minWidth: 220 },
  { title: "Administrators", key: "administrators", minWidth: 220 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: `Created At (${strTimeZone.value})`, key: "created_at", minWidth: 240 },
  { title: "Status", key: "status", minWidth: 200 },
  { title: "Actions", key: "actions", width: 112 },
]);

async function loadOrganizations(pageNumber: number = intRequestedPage): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getPlatformOrganizationList(appliedFilters, pageNumber);
    if (intCurrentRevision !== intRequestRevision) return;
    organizationPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    if ([401, 403].includes(requestError.value.statusCode)) {
      organizationPage.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function applyFilters(): void {
  appliedFilters = {
    name: strName.value,
    organizationId: strOrganizationId.value,
    statuses: [...arrStatus.value],
  };
  organizationPage.value = null;
  strUpdatedAt.value = null;
  void loadOrganizations(1);
}

function resetFilters(): void {
  strName.value = "";
  strOrganizationId.value = "";
  arrStatus.value = [];
  applyFilters();
}

onMounted(() => void loadOrganizations());

onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
