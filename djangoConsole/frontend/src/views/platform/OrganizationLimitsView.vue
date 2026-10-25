<!-- FileName: OrganizationLimitsView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">Usage &amp; Limits</h2>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading || boolDialog || !boolHasAccess"
      @click="loadLimits()">
      Refresh
    </v-btn>
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

  <v-alert
    v-if="strEditingUnavailable"
    type="warning"
    variant="tonal"
    class="mb-4"
    role="status">
    {{ strEditingUnavailable }}
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

    <div class="d-flex flex-wrap justify-end ga-2 mb-3">
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-pencil-outline"
        :disabled="boolLoading || boolDialog || !boolHasAccess || !!strEditingUnavailable"
        @click="openDialog()">
        Edit Limits
      </v-btn>

      <v-btn
        variant="tonal"
        prepend-icon="mdi-restore"
        :disabled="
          boolLoading ||
          boolDialog ||
          !boolHasAccess ||
          !!strEditingUnavailable ||
          !boolHasOverride
        "
        @click="openDialog(true)">
        Reset to Defaults
      </v-btn>
    </div>

    <p class="text-body-2 text-medium-emphasis text-end mb-3">
      Updated at {{ formatDateTime(usage.updated_at, strTimeZone) }}
    </p>
  </template>

  <OrganizationUsageTable
    :limits="usage?.limits ?? []"
    :loading="boolLoading"
    :error="requestError !== null"
    :warning="usage?.usage_warning" />

  <OrganizationLimitsDialog
    v-if="usage && boolDialog"
    :key="organizationId"
    :usage="usage"
    :reset="boolReset"
    @close="boolDialog = false"
    @refreshed="usage = $event"
    @saved="handleSaved"
    @unavailable="handleUnavailable" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import OrganizationUsageTable from "@/components/organizations/OrganizationUsageTable.vue";
import OrganizationLimitsDialog from "@/components/platform/OrganizationLimitsDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getPlatformOrganizationLimits } from "@/api/platformOrganizations";
import type { OrganizationLimitsResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ organizationId: string }>();
const sessionStore = useSessionStore();
const boolHasAccess = computed(
  () => sessionStore.authenticated && sessionStore.session?.user.is_platform_admin === true,
);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const usage = shallowRef<OrganizationLimitsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);
let intRequestRevision = 0;

const boolDialog = ref(false);
const boolReset = ref(false);
const strEditingUnavailable = ref("");
const boolHasOverride = computed(
  () => usage.value?.limits.some((limit) => limit.override !== null) ?? false,
);

async function loadLimits(): Promise<void> {
  if (!boolHasAccess.value || boolDialog.value) return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getPlatformOrganizationLimits(props.organizationId);
    if (intCurrentRevision !== intRequestRevision) return;
    usage.value = response;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    requestError.value = error;
    if ([401, 403, 404].includes(error.statusCode)) {
      usage.value = null;
      if (error.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openDialog(reset = false): void {
  if (
    !usage.value ||
    !boolHasAccess.value ||
    boolLoading.value ||
    boolDialog.value ||
    strEditingUnavailable.value ||
    (reset && !boolHasOverride.value)
  )
    return;
  strSuccess.value = "";
  boolReset.value = reset;
  boolDialog.value = true;
}

function handleSaved(): void {
  boolDialog.value = false;
  strSuccess.value = boolReset.value
    ? "Organization limits reset to defaults."
    : "Organization limits saved.";
  void loadLimits();
}

async function handleUnavailable(error: ApiError): Promise<void> {
  boolDialog.value = false;
  if (error.code === "organization_deleting") {
    strEditingUnavailable.value = `${error.message} Limits can no longer be changed.`;
  } else {
    usage.value = null;
    requestError.value = error;
    if (error.statusCode === 403) await sessionStore.refreshSession();
  }
}

watch(
  [() => props.organizationId, boolHasAccess],
  () => {
    intRequestRevision += 1;
    usage.value = null;
    requestError.value = null;
    boolDialog.value = false;
    boolLoading.value = false;
    strSuccess.value = "";
    strEditingUnavailable.value = "";
    void loadLimits();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
