<!-- FileName: OrganizationLimitsView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h1 class="text-h5">Usage &amp; Limits</h1>

    <div class="d-flex flex-wrap ga-2">
      <v-btn
        :to="{ name: 'platform-organizations' }"
        variant="text"
        prepend-icon="mdi-arrow-left"
        :disabled="dialogMode !== null">
        Back to Organizations
      </v-btn>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="dialogMode !== null"
        @click="loadLimits()">
        Refresh
      </v-btn>
    </div>
  </div>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="usage" class="mt-2">
      Previously loaded usage is shown and may be out of date.
    </p>
  </v-alert>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4" role="status">
    {{ strSuccess }}
  </v-alert>

  <template v-if="usage">
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <div class="text-subtitle-1">{{ usage.organization.name }}</div>
        <div class="text-body-2 text-medium-emphasis">
          Organization ID: {{ usage.organization.id }}
        </div>
      </v-card-text>
    </v-card>

    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-3">
      <p class="text-body-2 text-medium-emphasis">
        Updated at {{ formatDateTime(usage.updated_at, strTimeZone) }}
      </p>

      <div class="d-flex flex-wrap ga-2">
        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-pencil-outline"
          :disabled="boolLoading || dialogMode !== null"
          @click="openDialog(LimitDialog.Edit)">
          Edit Limits
        </v-btn>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-restore"
          :disabled="boolLoading || dialogMode !== null || !arrOverride.length"
          @click="openDialog(LimitDialog.Reset)">
          Reset to Defaults
        </v-btn>
      </div>
    </div>
  </template>

  <OrganizationUsageTable
    :limits="usage?.limits ?? []"
    :loading="boolLoading"
    :error="requestError !== null"
    :warning="usage?.usage_warning" />

  <v-dialog
    :model-value="dialogMode !== null"
    :persistent="boolSaving || boolLoading"
    :max-width="dialogMode === LimitDialog.Edit ? 1200 : 840"
    scrollable
    @update:model-value="closeDialog">
    <v-card v-if="usage">
      <v-card-title>
        {{ dialogMode === LimitDialog.Edit ? "Edit Limits" : "Reset to Defaults" }}
      </v-card-title>

      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="usage.organization.name"
              label="Organization"
              variant="outlined"
              readonly
              hide-details />
          </v-col>

          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="usage.organization.id"
              label="Organization ID"
              variant="outlined"
              readonly
              hide-details />
          </v-col>
        </v-row>

        <v-alert v-if="saveError" type="error" variant="tonal" class="mt-4" role="alert">
          {{ saveError.message }}
          <template v-if="boolRefreshRequired" #append>
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              :loading="boolLoading"
              @click="loadLimits(true)">
              Refresh Limits
            </v-btn>
          </template>
        </v-alert>

        <p v-if="dialogMode === LimitDialog.Reset" class="mt-4">
          Reset these limits to the current defaults? They will follow future default
          changes.
        </p>

        <v-alert
          v-if="boolLoweringLimits"
          type="warning"
          variant="tonal"
          class="mt-4"
          role="status">
          Lower limits restrict new activity. Existing files, queue items, and jobs are
          kept. Older logs and history may be removed under retention limits.
          <p v-if="arrOverLimit.length" class="mt-2">
            Below current use and reservations:
            {{ arrOverLimit.map((limit) => limit.label).join(", ") }}.
          </p>
        </v-alert>

        <v-form
          v-if="dialogMode === LimitDialog.Edit"
          id="organization-limits-form"
          class="mt-4"
          @submit.prevent="saveLimits">
          <v-table>
            <thead>
              <tr>
                <th scope="col">Resource</th>
                <th scope="col">Used</th>
                <th scope="col">Reserved</th>
                <th scope="col">Mode</th>
                <th scope="col">Limit</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="limit in arrEditLimit" :key="limit.key">
                <td class="py-3">{{ limit.label }}</td>
                <td class="text-no-wrap">
                  {{ formatOrganizationLimit(limit.used, limit.unit) }}
                </td>
                <td class="text-no-wrap">
                  {{ formatOrganizationLimit(limit.reserved, limit.unit) }}
                </td>
                <td class="py-3">
                  <v-select
                    v-model="limit.mode"
                    :items="ARR_MODE_OPTION"
                    :aria-label="`${limit.label} mode`"
                    min-width="200"
                    variant="outlined"
                    density="compact"
                    hide-details
                    :disabled="boolSaving || boolLoading || boolRefreshRequired" />
                </td>
                <td class="py-3">
                  <v-text-field
                    v-if="limit.mode === LimitMode.Override"
                    v-model="limit.input"
                    :aria-label="`${limit.label} limit`"
                    min-width="240"
                    type="number"
                    :step="limit.unit === LimitUnit.Bytes ? 'any' : 1"
                    :min="getInputValue(limit.minimum, limit.unit)"
                    :max="
                      limit.maximum === null
                        ? undefined
                        : getInputValue(limit.maximum, limit.unit)
                    "
                    :suffix="
                      limit.unit === LimitUnit.Bytes
                        ? 'MiB'
                        : limit.unit === LimitUnit.PerMinute
                          ? '/ min'
                          : undefined
                    "
                    :hint="`Default: ${formatOrganizationLimit(limit.default_limit, limit.unit)}`"
                    :error-messages="
                      getFieldErrors(saveError?.fields, `overrides.${limit.key}`)
                    "
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    :disabled="boolSaving || boolLoading || boolRefreshRequired" />
                  <v-text-field
                    v-else
                    :model-value="formatOrganizationLimit(limit.default_limit, limit.unit)"
                    :aria-label="`${limit.label} default`"
                    min-width="240"
                    variant="outlined"
                    density="compact"
                    readonly
                    hide-details />
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-form>

        <v-table v-else class="mt-4">
          <thead>
            <tr>
              <th scope="col">Resource</th>
              <th scope="col">Current Limit</th>
              <th scope="col">Default Limit</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="limit in arrOverride" :key="limit.key">
              <td>{{ limit.label }}</td>
              <td>{{ formatOrganizationLimit(limit.limit, limit.unit) }}</td>
              <td>{{ formatOrganizationLimit(limit.default_limit, limit.unit) }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolSaving || boolLoading" @click="closeDialog">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="
            boolLoading ||
            boolRefreshRequired ||
            (dialogMode === LimitDialog.Reset && !arrOverride.length)
          "
          @click="saveLimits">
          {{ dialogMode === LimitDialog.Edit ? "Save" : "Reset to Defaults" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import OrganizationUsageTable from "@/components/organizations/OrganizationUsageTable.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { ApiError, getApiError, getFieldErrors } from "@/api/errors";
import {
  getPlatformOrganizationLimits,
  updateOrganizationLimits,
} from "@/api/organizationLimits";
import {
  LimitUnit,
  type OrganizationLimitResponse,
  type OrganizationLimitsResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";
import { formatOrganizationLimit } from "@/app/organizationLimits";

enum LimitDialog {
  Edit = "edit",
  Reset = "reset",
}

enum LimitMode {
  Default = "default",
  Override = "override",
}

interface EditableLimit extends OrganizationLimitResponse {
  mode: LimitMode;
  input: string;
}

const ARR_MODE_OPTION = [
  { title: "Inherit Default", value: LimitMode.Default },
  { title: "Override", value: LimitMode.Override },
];
const INT_BYTES_PER_MIB = 1024 * 1024;

const props = defineProps<{ organizationId: string }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const usage = shallowRef<OrganizationLimitsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolRefreshRequired = ref(false);
const dialogMode = ref<LimitDialog | null>(null);
const arrEditLimit = ref<EditableLimit[]>([]);
let intRequestRevision = 0;

function getInputValue(value: number, unit: LimitUnit): string {
  return String(unit === LimitUnit.Bytes ? value / INT_BYTES_PER_MIB : value);
}

function getEditedValue(limit: EditableLimit): number {
  if (limit.mode === LimitMode.Default) return limit.default_limit;
  if (!String(limit.input).trim()) return NaN;
  const floatInput = Number(limit.input);
  if (!Number.isFinite(floatInput) || floatInput < 0) return NaN;
  if (limit.unit !== LimitUnit.Bytes) return floatInput;
  return Math.round(floatInput * INT_BYTES_PER_MIB);
}

const arrOverride = computed(
  () => usage.value?.limits.filter((limit) => limit.override !== null) ?? [],
);
const arrProposedLimit = computed(() =>
  dialogMode.value === LimitDialog.Reset
    ? arrOverride.value.map((limit) => ({ ...limit, proposed: limit.default_limit }))
    : arrEditLimit.value.map((limit) => ({ ...limit, proposed: getEditedValue(limit) })),
);
const arrOverLimit = computed(() =>
  arrProposedLimit.value.filter(
    (limit) => limit.proposed < (limit.used ?? 0) + (limit.reserved ?? 0),
  ),
);
const boolLoweringLimits = computed(
  () =>
    arrOverLimit.value.length > 0 ||
    arrProposedLimit.value.some((limit) => limit.proposed < limit.limit),
);

function prepareEditLimits(): void {
  arrEditLimit.value = (usage.value?.limits ?? []).map((limit) => ({
    ...limit,
    mode: limit.override === null ? LimitMode.Default : LimitMode.Override,
    input: getInputValue(limit.limit, limit.unit),
  }));
}

async function loadLimits(inDialog = false): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  if (inDialog) saveError.value = null;
  else requestError.value = null;
  try {
    const response = await getPlatformOrganizationLimits(props.organizationId);
    if (intCurrentRevision !== intRequestRevision) return;
    usage.value = response;
    if (inDialog) {
      prepareEditLimits();
      boolRefreshRequired.value = false;
    }
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    if (inDialog) saveError.value = error;
    else requestError.value = error;
    if ([401, 403, 404].includes(error.statusCode)) {
      usage.value = null;
      dialogMode.value = null;
      requestError.value = error;
      if (error.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openDialog(mode: LimitDialog): void {
  if (!usage.value || boolLoading.value || dialogMode.value !== null) return;
  strSuccess.value = "";
  saveError.value = null;
  boolRefreshRequired.value = false;
  prepareEditLimits();
  dialogMode.value = mode;
}

function closeDialog(): void {
  if (boolSaving.value || boolLoading.value) return;
  dialogMode.value = null;
  saveError.value = null;
}

async function saveLimits(): Promise<void> {
  if (
    !usage.value ||
    dialogMode.value === null ||
    boolSaving.value ||
    boolLoading.value ||
    boolRefreshRequired.value
  )
    return;

  const dictOverride: Record<string, number> = {};
  const dictFieldError: Record<string, string[]> = {};
  if (dialogMode.value === LimitDialog.Edit) {
    for (const limit of arrEditLimit.value) {
      if (limit.mode === LimitMode.Default) continue;
      const intValue = getEditedValue(limit);
      if (limit.unit === LimitUnit.Bytes && Number(limit.input) > 0 && intValue === 0) {
        dictFieldError[`overrides.${limit.key}`] = [
          "Value rounds to 0 B. Enter 0 or increase the size.",
        ];
        continue;
      }
      if (
        !Number.isSafeInteger(intValue) ||
        intValue < limit.minimum ||
        (limit.maximum !== null && intValue > limit.maximum)
      ) {
        const strRange =
          limit.maximum === null
            ? `at least ${formatOrganizationLimit(limit.minimum, limit.unit)}`
            : `from ${formatOrganizationLimit(limit.minimum, limit.unit)} to ${formatOrganizationLimit(limit.maximum, limit.unit)}`;
        dictFieldError[`overrides.${limit.key}`] = [
          `Enter ${limit.unit === LimitUnit.Bytes ? "a size" : "a whole number"} ${strRange}.`,
        ];
      } else dictOverride[limit.key] = intValue;
    }
  }
  if (Object.keys(dictFieldError).length) {
    saveError.value = new ApiError("Check the limits below.", { fields: dictFieldError });
    return;
  }

  const intCurrentRevision = ++intRequestRevision;
  const boolReset = dialogMode.value === LimitDialog.Reset;
  boolSaving.value = true;
  saveError.value = null;
  try {
    await updateOrganizationLimits(props.organizationId, {
      version: usage.value.version,
      overrides: dictOverride,
    });
    if (intCurrentRevision !== intRequestRevision) return;
    dialogMode.value = null;
    strSuccess.value = boolReset
      ? "Organization limits reset to defaults."
      : "Organization limits saved.";
    boolSaving.value = false;
    await loadLimits();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    saveError.value = getApiError(e);
    if (saveError.value.statusCode === 409) boolRefreshRequired.value = true;
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    if (intCurrentRevision === intRequestRevision) boolSaving.value = false;
  }
}

watch(
  () => props.organizationId,
  () => {
    usage.value = null;
    dialogMode.value = null;
    boolSaving.value = false;
    strSuccess.value = "";
    void loadLimits();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
