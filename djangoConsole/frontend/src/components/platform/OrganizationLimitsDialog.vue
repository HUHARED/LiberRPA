<!-- FileName: OrganizationLimitsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving || boolLoading"
    :max-width="!reset ? 1200 : 840"
    scrollable
    aria-labelledby="organization-limits-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="organization-limits-title">
        {{ !reset ? "Edit Limits" : "Reset to Defaults" }}
      </v-card-title>

      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="currentUsage.organization.name"
              label="Organization"
              variant="plain"
              readonly
              hide-details />
          </v-col>

          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="currentUsage.organization.id"
              label="Organization ID"
              variant="plain"
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
              @click="refreshLimits">
              Refresh Limits
            </v-btn>
          </template>
        </v-alert>

        <p v-if="reset" class="mt-4">
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
          v-if="!reset"
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
                    :disabled="boolSubmitBlocked" />
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
                    :disabled="boolSubmitBlocked" />
                  <v-text-field
                    v-else
                    :model-value="formatOrganizationLimit(limit.default_limit, limit.unit)"
                    :aria-label="`${limit.label} default`"
                    min-width="240"
                    variant="plain"
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
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving || boolLoading"
          @click="closeDialog">
          Cancel
        </v-btn>

        <v-spacer />

        <v-btn
          color="primary"
          variant="tonal"
          :prepend-icon="!reset ? 'mdi-content-save-outline' : 'mdi-restore'"
          :loading="boolSaving"
          :disabled="boolSubmitBlocked"
          @click="saveLimits">
          {{ !reset ? "Save" : "Reset to Defaults" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { ApiError, getApiError, getFieldErrors } from "@/api/errors";
import {
  getPlatformOrganizationLimits,
  updateOrganizationLimits,
} from "@/api/platformOrganizations";
import {
  LimitUnit,
  type OrganizationLimitResponse,
  type OrganizationLimitsResponse,
} from "@/api/generated/browserApi";

import { formatOrganizationLimit } from "@/app/organizationLimits";

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

const props = defineProps<{ usage: OrganizationLimitsResponse; reset: boolean }>();
const emit = defineEmits<{
  close: [];
  refreshed: [usage: OrganizationLimitsResponse];
  saved: [];
  unavailable: [error: ApiError];
}>();

const sessionStore = useSessionStore();
const boolHasAccess = computed(
  () => sessionStore.authenticated && sessionStore.session?.user.is_platform_admin === true,
);

const currentUsage = shallowRef(props.usage);
const arrEditLimit = ref<EditableLimit[]>([]);
const saveError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolRefreshRequired = ref(false);
let boolUnmounted = false;

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

const arrOverride = computed(() =>
  currentUsage.value.limits.filter((limit) => limit.override !== null),
);
const arrProposedLimit = computed(() =>
  props.reset
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
  arrEditLimit.value = currentUsage.value.limits.map((limit) => ({
    ...limit,
    mode: limit.override === null ? LimitMode.Default : LimitMode.Override,
    input: getInputValue(limit.limit, limit.unit),
  }));
}

const boolSubmitBlocked = computed(
  () =>
    !boolHasAccess.value ||
    boolSaving.value ||
    boolLoading.value ||
    boolRefreshRequired.value ||
    (props.reset && !arrOverride.value.length),
);

function showRequestError(error: ApiError): void {
  saveError.value = error;
  if (
    error.code === "organization_deleting" ||
    [401, 403, 404].includes(error.statusCode)
  ) {
    emit("unavailable", error);
  }
}

async function refreshLimits(): Promise<void> {
  if (boolUnmounted || !boolHasAccess.value || boolLoading.value || boolSaving.value)
    return;
  boolLoading.value = true;
  saveError.value = null;
  try {
    const response = await getPlatformOrganizationLimits(
      currentUsage.value.organization.id,
    );
    if (boolUnmounted) return;
    currentUsage.value = response;
    prepareEditLimits();
    boolRefreshRequired.value = false;
    emit("refreshed", response);
  } catch (e) {
    if (boolUnmounted) return;
    showRequestError(getApiError(e));
  } finally {
    if (!boolUnmounted) boolLoading.value = false;
  }
}

function closeDialog(): void {
  if (!boolLoading.value && !boolSaving.value) emit("close");
}

async function saveLimits(): Promise<void> {
  if (boolUnmounted || boolSubmitBlocked.value) return;

  const dictOverride: Record<string, number> = {};
  const dictFieldError: Record<string, string[]> = {};
  if (!props.reset) {
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

  boolSaving.value = true;
  saveError.value = null;
  try {
    await updateOrganizationLimits(currentUsage.value.organization.id, {
      version: currentUsage.value.version,
      overrides: dictOverride,
    });
    if (!boolUnmounted) emit("saved");
  } catch (e) {
    if (boolUnmounted) return;
    const error = getApiError(e);
    boolRefreshRequired.value = error.statusCode === 409 && error.code === "limits_changed";
    showRequestError(error);
  } finally {
    if (!boolUnmounted) boolSaving.value = false;
  }
}

prepareEditLimits();

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
