<!-- FileName: OrganizationsView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h1 class="text-h5">Organizations</h1>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading"
      aria-label="Refresh organization list"
      @click="loadOrganizations()">
      Refresh
    </v-btn>
  </div>

  <v-card
    variant="outlined"
    class="mb-6"
    :aria-busy="boolLoadingSettings || boolSavingSettings">
    <v-card-title>Organization Creation</v-card-title>

    <v-card-text>
      <v-progress-linear
        v-if="boolLoadingSettings"
        indeterminate
        color="primary"
        class="mb-4"
        aria-label="Loading organization creation setting" />

      <v-alert
        v-if="settingsRequestError"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        {{ settingsRequestError.message }}
        <template #append>
          <v-btn
            variant="tonal"
            prepend-icon="mdi-refresh"
            size="small"
            :disabled="boolSettingsActionBlocked"
            @click="loadSettings">
            Retry
          </v-btn>
        </template>
      </v-alert>

      <v-alert
        v-if="settingsSaveError"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        Save was not confirmed. {{ settingsSaveError.message }}
        <template v-if="!serviceSettings" #append>
          <v-btn
            variant="tonal"
            prepend-icon="mdi-refresh"
            size="small"
            :disabled="boolSettingsActionBlocked"
            @click="loadSettings">
            Retry
          </v-btn>
        </template>
      </v-alert>

      <v-alert
        v-if="strSettingsSuccess && !boolSettingsChanged"
        type="success"
        variant="tonal"
        class="mb-4"
        role="status">
        {{ strSettingsSuccess }}
      </v-alert>

      <v-form
        v-if="serviceSettings"
        id="organization-creation-form"
        @submit.prevent="saveSettings">
        <v-switch
          v-model="boolAllowOrganizationCreation"
          label="Allow Organization Creation"
          true-icon="mdi-check"
          color="primary"
          :disabled="boolSettingsActionBlocked"
          :error-messages="settingsSaveError?.fields.allow_organization_creation ?? []"
          hint="Existing accounts and valid invitations are unaffected."
          persistent-hint />
      </v-form>
    </v-card-text>

    <v-card-actions v-if="serviceSettings">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-close"
        :disabled="boolSettingsActionBlocked || !boolSettingsChanged"
        @click="cancelSettings">
        Cancel
      </v-btn>

      <v-spacer />

      <v-btn
        type="submit"
        form="organization-creation-form"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-content-save-outline"
        :loading="boolSavingSettings"
        :disabled="boolSettingsActionBlocked || !boolSettingsChanged">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form aria-label="Organization filters" @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="strName"
              label="Name"
              placeholder="Search by name"
              maxlength="200"
              variant="underlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="strOrganizationId"
              label="Organization ID"
              placeholder="Full organization ID"
              maxlength="36"
              variant="underlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" md="4">
            <v-select
              v-model="arrStatus"
              :items="ARR_STATUS_OPTION"
              label="Status"
              placeholder="All statuses"
              persistent-placeholder
              multiple
              chips
              closable-chips
              clearable
              variant="underlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>
        </v-row>

        <div class="d-flex ga-2 mt-4">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            :disabled="boolLoading"
            @click="resetFilters">
            Reset Filters
          </v-btn>

          <v-spacer />

          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-check"
            :disabled="boolLoading">
            Apply
          </v-btn>
        </div>
      </form>
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
      :headers="ARR_HEADER"
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
            name: 'platform-organization-details',
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
import {
  getServiceSettings,
  updateServiceSettings,
  getPlatformOrganizationList,
} from "@/api/platformOrganizations";
import {
  INT_LIST_PAGE_SIZE,
  PlatformOrganizationStatus,
  type PlatformOrganizationListResponse,
  type ServiceSettingsResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const ARR_STATUS_OPTION = [
  { title: "Active", value: PlatformOrganizationStatus.Active },
  { title: "Suspended", value: PlatformOrganizationStatus.Suspended },
  { title: "Deletion Scheduled", value: PlatformOrganizationStatus.DeletionScheduled },
  { title: "Deletion in Progress", value: PlatformOrganizationStatus.DeletionInProgress },
];

const sessionStore = useSessionStore();
const boolCanManage = computed(() => sessionStore.session?.user.is_platform_admin === true);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const serviceSettings = shallowRef<ServiceSettingsResponse | null>(null);
const boolAllowOrganizationCreation = ref(false);
const boolSettingsChanged = computed(
  () =>
    serviceSettings.value !== null &&
    boolAllowOrganizationCreation.value !==
      serviceSettings.value.allow_organization_creation,
);
const settingsRequestError = shallowRef<ApiError | null>(null);
const settingsSaveError = shallowRef<ApiError | null>(null);
const strSettingsSuccess = ref("");
const boolLoadingSettings = ref(false);
const boolSavingSettings = ref(false);
const boolSettingsActionBlocked = computed(
  () =>
    boolLoadingSettings.value ||
    boolSavingSettings.value ||
    sessionStore.busy ||
    !boolCanManage.value,
);

const strName = ref<string | null>("");
const strOrganizationId = ref<string | null>("");
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
let boolUnmounted = false;

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 220 },
  { title: "Administrators", key: "administrators", minWidth: 220 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: "Created At", key: "created_at", minWidth: 240 },
  { title: "Status", key: "status", minWidth: 200 },
];

function applySettings(response: ServiceSettingsResponse): void {
  serviceSettings.value = response;
  boolAllowOrganizationCreation.value = response.allow_organization_creation;
}

function cancelSettings(): void {
  if (boolSettingsActionBlocked.value || !serviceSettings.value) return;
  applySettings(serviceSettings.value);
  settingsSaveError.value = null;
  strSettingsSuccess.value = "";
}

async function loadSettings(): Promise<void> {
  if (boolUnmounted || boolSettingsActionBlocked.value) return;
  boolLoadingSettings.value = true;
  settingsRequestError.value = null;
  settingsSaveError.value = null;
  strSettingsSuccess.value = "";
  try {
    const response = await getServiceSettings();
    if (boolUnmounted || !boolCanManage.value) return;
    applySettings(response);
  } catch (e) {
    if (boolUnmounted) return;
    settingsRequestError.value = getApiError(e);
    if (settingsRequestError.value.statusCode === 401) {
      serviceSettings.value = null;
      boolAllowOrganizationCreation.value = false;
    }
    if (settingsRequestError.value.statusCode === 403) {
      if (settingsRequestError.value.code === "platform_access_required")
        await sessionStore.refreshChangedSession();
      else await sessionStore.refreshSession();
    }
  } finally {
    if (!boolUnmounted) boolLoadingSettings.value = false;
  }
}

async function saveSettings(): Promise<void> {
  if (boolUnmounted || boolSettingsActionBlocked.value || !boolSettingsChanged.value)
    return;
  boolSavingSettings.value = true;
  settingsSaveError.value = null;
  strSettingsSuccess.value = "";
  try {
    const response = await updateServiceSettings({
      allow_organization_creation: boolAllowOrganizationCreation.value,
    });
    if (boolUnmounted || !boolCanManage.value) return;
    applySettings(response);
    strSettingsSuccess.value = "Organization creation setting saved.";
  } catch (e) {
    if (boolUnmounted) return;
    settingsSaveError.value = getApiError(e);
    if (settingsSaveError.value.statusCode === 401) {
      serviceSettings.value = null;
      boolAllowOrganizationCreation.value = false;
    }
    if (settingsSaveError.value.statusCode === 403) {
      if (settingsSaveError.value.code === "platform_access_required")
        await sessionStore.refreshChangedSession();
      else await sessionStore.refreshSession();
    }
  } finally {
    if (!boolUnmounted) boolSavingSettings.value = false;
  }
}

async function loadOrganizations(pageNumber: number = intRequestedPage): Promise<void> {
  if (boolUnmounted || !boolCanManage.value) return;
  const intCurrentRevision = ++intRequestRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getPlatformOrganizationList(appliedFilters, pageNumber);
    if (intCurrentRevision !== intRequestRevision || !boolCanManage.value) return;
    organizationPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    if (requestError.value.code === "organization_page_not_found" && pageNumber > 1) {
      await loadOrganizations(1);
      return;
    }
    if (requestError.value.statusCode === 401) {
      organizationPage.value = null;
      strUpdatedAt.value = null;
    }
    if (requestError.value.statusCode === 403) {
      if (requestError.value.code === "platform_access_required")
        await sessionStore.refreshChangedSession();
      else await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function applyFilters(): void {
  if (boolLoading.value) return;
  appliedFilters = {
    name: (strName.value ?? "").trim(),
    organizationId: (strOrganizationId.value ?? "").trim(),
    statuses: [...arrStatus.value],
  };
  organizationPage.value = null;
  strUpdatedAt.value = null;
  void loadOrganizations(1);
}

function resetFilters(): void {
  if (boolLoading.value) return;
  strName.value = "";
  strOrganizationId.value = "";
  arrStatus.value = [];
  applyFilters();
}

onMounted(() => {
  void loadSettings();
  void loadOrganizations();
});

onBeforeUnmount(() => {
  boolUnmounted = true;
  intRequestRevision += 1;
});
</script>

<style scoped></style>
