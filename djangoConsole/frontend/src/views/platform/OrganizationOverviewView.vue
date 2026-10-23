<!-- FileName: OrganizationOverviewView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">Overview</h2>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading || serviceTarget !== null"
      @click="loadOrganization()">
      Refresh
    </v-btn>
  </div>

  <v-progress-linear v-if="boolLoading" indeterminate color="primary" class="mb-4" />

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="organization" class="mt-2">Previously loaded details may be out of date.</p>
  </v-alert>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4" role="status">
    {{ strSuccess }}
  </v-alert>

  <template v-if="organization">
    <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
      Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
    </p>

    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Organization</v-card-title>

      <v-card-text>
        <v-row>
          <v-col v-for="field in arrInformationField" :key="field.label" cols="12" sm="6">
            <v-text-field
              :model-value="field.value"
              :label="field.label"
              variant="plain"
              readonly
              hide-details />
          </v-col>

          <v-col cols="12">
            <v-textarea
              :model-value="organization.notes || '—'"
              label="Notes"
              variant="plain"
              rows="2"
              auto-grow
              readonly
              hide-details />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Service Status</v-card-title>

      <v-card-text>
        <div class="d-flex flex-wrap ga-2 mb-4">
          <v-chip
            v-if="
              !organization.suspended_at &&
              !organization.deletion_requested_at &&
              !organization.deletion_started_at
            "
            color="success"
            size="small"
            variant="tonal">
            Active
          </v-chip>
          <v-chip
            v-if="organization.suspended_at"
            color="warning"
            size="small"
            variant="tonal">
            Suspended
          </v-chip>
          <v-chip
            v-if="organization.deletion_started_at"
            color="error"
            size="small"
            variant="tonal">
            Deletion in Progress
          </v-chip>
          <v-chip
            v-else-if="organization.deletion_requested_at"
            color="warning"
            size="small"
            variant="tonal">
            Deletion Scheduled
          </v-chip>
        </div>

        <v-row>
          <v-col v-for="field in arrStateField" :key="field.label" cols="12" sm="6">
            <v-text-field
              :model-value="field.value"
              :label="field.label"
              variant="plain"
              readonly
              hide-details />
          </v-col>
        </v-row>

        <p v-if="organization.deletion_started_at" class="mt-4 text-medium-emphasis">
          Service status cannot be changed while deletion is in progress.
        </p>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn
          :color="organization.suspended_at ? 'primary' : 'warning'"
          variant="tonal"
          :prepend-icon="
            organization.suspended_at
              ? 'mdi-play-circle-outline'
              : 'mdi-pause-circle-outline'
          "
          :disabled="
            boolLoading ||
            serviceTarget !== null ||
            organization.deletion_started_at !== null
          "
          @click="openServiceDialog">
          {{ organization.suspended_at ? "Resume Service" : "Suspend Service" }}
        </v-btn>
      </v-card-actions>
    </v-card>

    <v-card variant="outlined">
      <v-card-title>Administrators</v-card-title>

      <v-card-text>
        <v-table v-if="organization.administrators.length">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="administrator in organization.administrators"
              :key="administrator.id">
              <td>{{ administrator.name || "—" }}</td>
              <td>{{ administrator.email }}</td>
            </tr>
          </tbody>
        </v-table>
        <p v-else>No active administrators.</p>
      </v-card-text>
    </v-card>
  </template>

  <OrganizationServiceDialog
    v-if="serviceTarget"
    :key="serviceTarget.id"
    :organization="serviceTarget"
    @close="serviceTarget = null"
    @refreshed="applyOrganization"
    @saved="handleServiceSaved"
    @unavailable="handleOrganizationUnavailable" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import OrganizationServiceDialog from "@/components/platform/OrganizationServiceDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getPlatformOrganizationDetails } from "@/api/platformOrganizations";
import type { PlatformOrganizationDetailsResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ organizationId: string }>();
const sessionStore = useSessionStore();
const boolHasAccess = computed(() => !!sessionStore.session?.user.is_platform_admin);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const organization = shallowRef<PlatformOrganizationDetailsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const strUpdatedAt = ref<string | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);

const serviceTarget = shallowRef<PlatformOrganizationDetailsResponse | null>(null);

const arrInformationField = computed(() =>
  organization.value
    ? [
        { label: "Name", value: organization.value.name },
        { label: "Organization ID", value: organization.value.id },
        { label: "Default Time Zone", value: organization.value.default_time_zone },
        {
          label: "Created At",
          value: formatDateTime(organization.value.created_at, strTimeZone.value),
        },
      ]
    : [],
);
const arrStateField = computed(() =>
  organization.value
    ? [
        {
          label: "Suspended At",
          value: formatDateTime(organization.value.suspended_at, strTimeZone.value),
        },
        {
          label: "Deletion Requested At",
          value: formatDateTime(
            organization.value.deletion_requested_at,
            strTimeZone.value,
          ),
        },
        {
          label: "Deletion Due At",
          value: formatDateTime(organization.value.deletion_due_at, strTimeZone.value),
        },
        {
          label: "Deletion Started At",
          value: formatDateTime(organization.value.deletion_started_at, strTimeZone.value),
        },
      ]
    : [],
);
let intRequestRevision = 0;

function applyOrganization(response: PlatformOrganizationDetailsResponse): void {
  organization.value = response;
  requestError.value = null;
  strUpdatedAt.value = new Date().toISOString();
}

async function handleOrganizationUnavailable(error: ApiError): Promise<void> {
  organization.value = null;
  serviceTarget.value = null;
  strUpdatedAt.value = null;
  requestError.value = error;
  if (error.statusCode === 403) await sessionStore.refreshSession();
}

async function loadOrganization(): Promise<void> {
  if (!boolHasAccess.value) return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getPlatformOrganizationDetails(props.organizationId);
    if (intCurrentRevision !== intRequestRevision) return;
    applyOrganization(response);
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    if ([401, 403, 404].includes(error.statusCode))
      await handleOrganizationUnavailable(error);
    else requestError.value = error;
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openServiceDialog(): void {
  if (
    !organization.value ||
    boolLoading.value ||
    serviceTarget.value ||
    organization.value.deletion_started_at
  )
    return;
  serviceTarget.value = organization.value;
  strSuccess.value = "";
}

function handleServiceSaved(response: PlatformOrganizationDetailsResponse): void {
  applyOrganization(response);
  strSuccess.value = response.suspended_at
    ? "Organization service suspended."
    : "Organization service resumed.";
  serviceTarget.value = null;
}

watch(
  [() => props.organizationId, boolHasAccess],
  () => {
    intRequestRevision += 1;
    organization.value = null;
    serviceTarget.value = null;
    requestError.value = null;
    strUpdatedAt.value = null;
    strSuccess.value = "";
    boolLoading.value = false;
    void loadOrganization();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
