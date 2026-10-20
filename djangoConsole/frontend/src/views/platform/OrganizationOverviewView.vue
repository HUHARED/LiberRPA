<!-- FileName: OrganizationOverviewView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">Overview</h2>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading || boolSaving || serviceTarget !== null"
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
              variant="underlined"
              readonly
              hide-details />
          </v-col>

          <v-col cols="12">
            <v-textarea
              :model-value="organization.notes || '—'"
              label="Notes"
              variant="underlined"
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
              variant="underlined"
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
          :disabled="boolLoading || boolSaving || organization.deletion_started_at !== null"
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

  <v-dialog
    :model-value="serviceTarget !== null"
    :persistent="boolSaving || boolLoading"
    max-width="720"
    scrollable
    @update:model-value="!$event && closeServiceDialog()">
    <v-card v-if="serviceTarget">
      <v-card-title>{{ boolSuspend ? "Suspend Service" : "Resume Service" }}</v-card-title>

      <v-card-text>
        <v-text-field
          :model-value="serviceTarget.name"
          label="Organization"
          variant="underlined"
          readonly
          hide-details
          class="mb-4" />

        <v-text-field
          :model-value="serviceTarget.id"
          label="Organization ID"
          variant="underlined"
          readonly
          hide-details
          class="mb-4" />

        <v-alert :type="boolSuspend ? 'warning' : 'info'" variant="tonal" class="mb-4">
          <template v-if="boolSuspend">
            Suspend all Console business requests for this organization, including Executor
            heartbeats and result reports. Waiting work will not resume after service is
            restored. Running processes may continue on their computers.
          </template>
          <template v-else>
            Allow eligible new business requests. Previously canceled work and missed
            Schedule triggers will not run again. A scheduled organization deletion will
            remain in place.
          </template>
        </v-alert>

        <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ saveError.message }}
          <div v-if="boolRefreshRequired" class="mt-3">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              :loading="boolLoading"
              :disabled="boolSaving || boolLoading"
              @click="loadOrganization(true)">
              Refresh Organization
            </v-btn>
          </div>
        </v-alert>

        <v-alert v-if="strServiceUnavailable" type="info" variant="tonal" class="mb-4">
          {{ strServiceUnavailable }}
        </v-alert>

        <v-form id="organization-service-form" @submit.prevent="saveService">
          <v-textarea
            v-model="strReason"
            label="Reason"
            variant="outlined"
            rows="3"
            auto-grow
            :counter="INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH"
            :counter-value="(value) => Array.from(value).length"
            :error-messages="saveError?.fields.reason ?? []"
            :disabled="
              boolSaving || boolLoading || boolRefreshRequired || !!strServiceUnavailable
            "
            hint="Recorded in the platform audit log. Not included in the email to administrators."
            persistent-hint />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolSaving || boolLoading" @click="closeServiceDialog">
          Cancel
        </v-btn>
        <v-btn
          type="submit"
          form="organization-service-form"
          :color="boolSuspend ? 'warning' : 'primary'"
          variant="tonal"
          :loading="boolSaving"
          :disabled="
            boolLoading ||
            boolRefreshRequired ||
            !!strServiceUnavailable ||
            !strReason.trim()
          ">
          {{ boolSuspend ? "Suspend Service" : "Resume Service" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { ApiError, getApiError } from "@/api/errors";
import {
  getPlatformOrganizationDetails,
  updateOrganizationService,
} from "@/api/organizationLimits";
import {
  INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH,
  type PlatformOrganizationDetailsResponse,
} from "@/api/generated/browserApi";

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
const boolSuspend = ref(false);
const strReason = ref("");
const saveError = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
const boolRefreshRequired = ref(false);

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
const strServiceUnavailable = computed(() => {
  if (!serviceTarget.value) return "";
  if (serviceTarget.value.deletion_started_at)
    return "Organization deletion is in progress.";
  if ((serviceTarget.value.suspended_at !== null) === boolSuspend.value)
    return boolSuspend.value
      ? "Service is already suspended."
      : "Service is already resumed.";
  return "";
});

let intRequestRevision = 0;

async function loadOrganization(inDialog = false): Promise<void> {
  if (!boolHasAccess.value || boolSaving.value) return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  if (inDialog) saveError.value = null;
  else requestError.value = null;
  try {
    const response = await getPlatformOrganizationDetails(props.organizationId);
    if (intCurrentRevision !== intRequestRevision) return;
    organization.value = response;
    requestError.value = null;
    strUpdatedAt.value = new Date().toISOString();
    if (inDialog) {
      serviceTarget.value = response;
      boolRefreshRequired.value = false;
    }
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    if (inDialog) saveError.value = error;
    else requestError.value = error;
    if ([401, 403, 404].includes(error.statusCode)) {
      organization.value = null;
      serviceTarget.value = null;
      strUpdatedAt.value = null;
      requestError.value = error;
      if (error.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openServiceDialog(): void {
  if (
    !organization.value ||
    boolLoading.value ||
    boolSaving.value ||
    organization.value.deletion_started_at
  )
    return;
  serviceTarget.value = organization.value;
  boolSuspend.value = organization.value.suspended_at === null;
  strReason.value = "";
  strSuccess.value = "";
  saveError.value = null;
  boolRefreshRequired.value = false;
}

function closeServiceDialog(): void {
  if (boolLoading.value || boolSaving.value) return;
  serviceTarget.value = null;
  saveError.value = null;
}

async function saveService(): Promise<void> {
  if (
    !boolHasAccess.value ||
    !serviceTarget.value ||
    boolLoading.value ||
    boolSaving.value ||
    boolRefreshRequired.value ||
    strServiceUnavailable.value
  )
    return;
  const strTrimmedReason = strReason.value.trim();
  if (
    !strTrimmedReason ||
    Array.from(strTrimmedReason).length > INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH
  ) {
    saveError.value = new ApiError("Enter a reason for this change.", {
      fields: {
        reason: [`Enter 1 to ${INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH} characters.`],
      },
    });
    return;
  }

  const intCurrentRevision = ++intRequestRevision;
  boolSaving.value = true;
  saveError.value = null;
  try {
    const response = await updateOrganizationService(serviceTarget.value.id, {
      suspended: boolSuspend.value,
      reason: strTrimmedReason,
      expected_suspended_at: serviceTarget.value.suspended_at,
      expected_deletion_requested_at: serviceTarget.value.deletion_requested_at,
    });
    if (intCurrentRevision !== intRequestRevision) return;
    organization.value = response;
    requestError.value = null;
    strUpdatedAt.value = new Date().toISOString();
    strSuccess.value = boolSuspend.value
      ? "Organization service suspended."
      : "Organization service resumed.";
    serviceTarget.value = null;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    saveError.value = error;
    if (error.statusCode === 409) boolRefreshRequired.value = true;
    if ([401, 403, 404].includes(error.statusCode)) {
      organization.value = null;
      serviceTarget.value = null;
      strUpdatedAt.value = null;
      requestError.value = error;
      if (error.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolSaving.value = false;
  }
}

watch(
  [() => props.organizationId, boolHasAccess],
  () => {
    intRequestRevision += 1;
    organization.value = null;
    serviceTarget.value = null;
    requestError.value = null;
    saveError.value = null;
    strUpdatedAt.value = null;
    strSuccess.value = "";
    boolSaving.value = false;
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
