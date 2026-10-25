<!-- FileName: OrganizationUsageView.vue -->
<template>
  <div class="d-flex align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">Usage &amp; Retention</h2>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolSaving"
      @click="loadUsage">
      Refresh
    </v-btn>
  </div>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="usage" class="mt-2">
      Previously loaded usage is shown and may be out of date.
    </p>
  </v-alert>

  <p v-if="usage" class="text-body-2 text-medium-emphasis text-end mb-3">
    Updated at {{ formatDateTime(usage.updated_at, strTimeZone) }}
  </p>

  <h3 class="text-subtitle-1 mb-2">Usage</h3>
  <OrganizationUsageTable
    :limits="usage?.limits ?? []"
    :loading="boolLoading"
    :error="requestError !== null"
    :warning="usage?.usage_warning"
    show-actions />

  <template v-if="usage">
    <h3 class="text-subtitle-1 mt-6 mb-2">Retention</h3>
    <p class="text-body-2 text-medium-emphasis mb-3">
      Capacity limits may remove eligible logs and history before these periods end.
    </p>
    <v-card variant="outlined">
      <v-card-text>
        <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ saveError.message }}
        </v-alert>

        <v-alert
          v-if="strSuccess"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ strSuccess }}
        </v-alert>

        <v-form
          id="organization-retention-form"
          validate-on="submit"
          @submit.prevent="saveRetention">
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strRunLogDays"
                label="Run Log Retention"
                type="number"
                suffix="days"
                variant="outlined"
                :min="1"
                :max="usage.retention.run_log_max_days"
                :step="1"
                :rules="[validateRunLogDays]"
                :error-messages="saveError?.fields.run_log_days ?? []"
                :disabled="boolActionBlocked"
                :hint="`Maximum: ${usage.retention.run_log_max_days} days.`"
                persistent-hint
                required
                @update:model-value="
                  saveError = null;
                  strSuccess = '';
                " />
            </v-col>
          </v-row>

          <v-alert
            v-if="boolShortening"
            type="warning"
            variant="tonal"
            class="mt-3"
            role="status">
            Shortening retention may remove older Run Logs. Removed logs cannot be restored.
          </v-alert>
        </v-form>
      </v-card-text>

      <v-table>
        <thead>
          <tr>
            <th scope="col">Resource</th>
            <th scope="col">Retention</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Run History</td>
            <td>{{ usage.retention.run_history_days }} days</td>
          </tr>
          <tr>
            <td>Audit Log</td>
            <td>{{ usage.retention.audit_days }} days</td>
          </tr>
        </tbody>
      </v-table>

      <v-card-actions>
        <v-spacer />
        <v-btn
          type="submit"
          form="organization-retention-form"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-content-save-outline"
          :loading="boolSaving"
          :disabled="boolActionBlocked || !boolChanged">
          Save Retention
        </v-btn>
      </v-card-actions>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import OrganizationUsageTable from "@/components/organizations/OrganizationUsageTable.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getOrganizationUsage, updateOrganizationRetention } from "@/api/organization";
import type { OrganizationLimitsResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);

const usage = shallowRef<OrganizationLimitsResponse | null>(null);
const strRunLogDays = ref("");
const boolChanged = computed(
  () =>
    usage.value !== null &&
    Number(strRunLogDays.value) !== usage.value.retention.run_log_days,
);
const boolShortening = computed(
  () =>
    usage.value !== null &&
    strRunLogDays.value.trim() !== "" &&
    Number(strRunLogDays.value) >= 1 &&
    Number(strRunLogDays.value) < usage.value.retention.run_log_days,
);

const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolActionBlocked = computed(
  () => boolLoading.value || boolSaving.value || sessionStore.busy || !boolCanManage.value,
);

let intRequestRevision = 0;
let boolUnmounted = false;

async function loadUsage(): Promise<void> {
  if (boolUnmounted || boolSaving.value) return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getOrganizationUsage();
    if (intCurrentRevision !== intRequestRevision) return;
    if (!boolChanged.value) strRunLogDays.value = String(response.retention.run_log_days);
    usage.value = response;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    if ([401, 403].includes(requestError.value.statusCode)) {
      usage.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function validateRunLogDays(value: string | number | null): true | string {
  const intDays = Number(value);
  const intMaximum = usage.value?.retention.run_log_max_days ?? 0;
  return String(value ?? "").trim() &&
    Number.isInteger(intDays) &&
    intDays >= 1 &&
    intDays <= intMaximum
    ? true
    : `Enter a whole number from 1 to ${intMaximum}.`;
}

async function saveRetention(event: SubmitEventPromise): Promise<void> {
  if (boolUnmounted || boolActionBlocked.value || !boolChanged.value) return;
  const validation = await event;
  if (!validation.valid || boolUnmounted || boolActionBlocked.value || !boolChanged.value)
    return;
  const intCurrentRevision = ++intRequestRevision;
  const intDays = Number(strRunLogDays.value);
  boolSaving.value = true;
  saveError.value = null;
  strSuccess.value = "";
  try {
    const response = await updateOrganizationRetention({ run_log_days: intDays });
    if (intCurrentRevision !== intRequestRevision) return;
    if (usage.value) {
      usage.value = {
        ...usage.value,
        retention: { ...usage.value.retention, run_log_days: intDays },
      };
    }
    strRunLogDays.value = String(intDays);
    strSuccess.value = response.message;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    saveError.value = getApiError(e);
    if ([401, 403].includes(saveError.value.statusCode)) {
      requestError.value = saveError.value;
      usage.value = null;
      if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolSaving.value = false;
  }
}

onMounted(() => void loadUsage());

onBeforeUnmount(() => {
  boolUnmounted = true;
  intRequestRevision += 1;
});
</script>

<style scoped></style>
