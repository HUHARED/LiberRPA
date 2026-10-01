<!-- FileName: AuditLogView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h6 mb-2">Audit Log</h2>
      <p class="text-medium-emphasis">
        Retained activity in your organization, newest first.
      </p>
    </v-col>
    <v-col cols="auto">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="loadRecords(undefined, true)">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form aria-label="Audit filters" @submit.prevent="applyFilters">
        <p class="mb-4">
          Time range uses {{ strTimeZone }} and includes both selected dates.
        </p>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field
              v-model="draftFilters.fromDate"
              type="date"
              label="From Date"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :error-messages="requestError?.fields.date_from ?? []"
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              v-model="draftFilters.toDate"
              type="date"
              label="Through Date"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :error-messages="requestError?.fields.date_to ?? []"
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-autocomplete
              v-model="draftFilters.actorIds"
              :items="arrActorOption"
              label="Actor"
              placeholder="All actors"
              persistent-placeholder
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-autocomplete
              v-model="draftFilters.modules"
              :items="arrModuleOption"
              label="Module"
              placeholder="All modules"
              persistent-placeholder
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-autocomplete
              v-model="draftFilters.actions"
              :items="arrActionOption"
              label="Action"
              placeholder="All actions"
              persistent-placeholder
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-select
              v-model="draftFilters.results"
              :items="ARR_AUDIT_RESULT"
              label="Result"
              placeholder="All results"
              persistent-placeholder
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>
        </v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal" :disabled="boolLoading">
            Apply
          </v-btn>
          <v-btn variant="outlined" :disabled="boolLoading" @click="resetFilters">
            Reset
          </v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="recordPage" class="mt-2">
      Previously loaded results are shown. Refresh to try again.
    </p>
  </v-alert>
  <div
    class="d-flex flex-wrap justify-space-between ga-2 mb-3 text-body-2 text-medium-emphasis">
    <span>Time zone: {{ strTimeZone }}</span>
    <span v-if="strUpdatedAt">
      Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
    </span>
  </div>
  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="recordPage?.records ?? []"
      :items-length="recordPage?.pagination.total_count ?? 0"
      :items-per-page="recordPage?.pagination.page_size ?? 50"
      :page="recordPage?.pagination.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading audit records…"
      disable-sort
      hide-default-footer>
      <template #item.created_at="{ item }">
        {{ formatDateTime(item.created_at, strTimeZone) }}
      </template>
      <template #item.actor_name="{ item }">
        <div class="table-text-narrow">{{ item.actor_name }}</div>
      </template>
      <template #item.channel="{ item }">{{ AUDIT_CHANNEL_LABEL[item.channel] }}</template>
      <template #item.action="{ item }">
        <div class="table-text-narrow">{{ formatAuditLabel(item.action) }}</div>
      </template>
      <template #item.object="{ item }">
        <div class="table-text">
          {{ formatAuditLabel(item.object_type) }}:
          {{ item.object_name || item.object_id || "—" }}
        </div>
      </template>
      <template #item.result="{ item }">
        <v-chip :color="item.result === 'succeeded' ? 'success' : 'error'" size="small">
          {{ formatAuditLabel(item.result) }}
        </v-chip>
      </template>
      <template #item.actions="{ item }">
        <v-btn variant="text" size="small" @click="strDetailsId = item.id">
          View Details
        </v-btn>
      </template>
      <template #no-data>
        {{
          requestError
            ? "The audit list could not be loaded."
            : "No audit records match the current filters."
        }}
      </template>
    </v-data-table-server>
    <template v-if="recordPage">
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ recordPage.pagination.total_count }} records · Page
          {{ recordPage.pagination.page }} of {{ recordPage.pagination.total_pages }}
        </p>
        <v-pagination
          v-if="recordPage.pagination.total_pages > 1"
          :model-value="recordPage.pagination.page"
          :length="recordPage.pagination.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          density="comfortable"
          aria-label="Audit pages"
          @update:model-value="loadRecords" />
      </div>
    </template>
  </v-card>
  <AuditDetailsDialog
    v-if="strDetailsId"
    :audit-id="strDetailsId"
    @close="strDetailsId = null" />
</template>

<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  shallowRef,
  watch,
} from "vue";

import AuditDetailsDialog from "../components/AuditDetailsDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { type AuditListFilters, getAuditList, getAuditFilterOptions } from "../api/audit";
import type {
  AuditFilterOptionsResponse,
  AuditListResponse,
} from "../api/generated/browserApi";
import { AUDIT_CHANNEL_LABEL, ARR_AUDIT_RESULT, formatAuditLabel } from "../app/audit";
import { formatDateTime } from "../app/formatters";

const ARR_HEADER = [
  { title: "Time", key: "created_at", minWidth: 180 },
  { title: "Actor", key: "actor_name", minWidth: 180 },
  { title: "Channel", key: "channel", minWidth: 100 },
  { title: "Action", key: "action", minWidth: 180 },
  { title: "Object", key: "object", minWidth: 200 },
  { title: "Result", key: "result", minWidth: 110 },
  { title: "Actions", key: "actions", minWidth: 100 },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const draftFilters = reactive<Omit<AuditListFilters, "timeZone">>({
  fromDate: "",
  toDate: "",
  actorIds: [],
  modules: [],
  actions: [],
  results: [],
});
const recordPage = shallowRef<AuditListResponse | null>(null);
const filterOptions = shallowRef<AuditFilterOptionsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strUpdatedAt = ref<string | null>(null);
const strDetailsId = ref<string | null>(null);
const arrActorOption = computed(() =>
  (filterOptions.value?.actors ?? []).map((actor) => ({
    title: actor.name,
    value: actor.id ?? "system",
  })),
);
const arrModuleOption = computed(() =>
  (filterOptions.value?.modules ?? []).map((module) => ({
    title: formatAuditLabel(module),
    value: module,
  })),
);
const arrActionOption = computed(() =>
  (filterOptions.value?.actions ?? []).map((action) => ({
    title: formatAuditLabel(action),
    value: action,
  })),
);
let appliedFilters = buildFilters();
let intRequestedPage = 1;
let intListRevision = 0;

function buildFilters(): AuditListFilters {
  return {
    fromDate: draftFilters.fromDate,
    toDate: draftFilters.toDate,
    timeZone: strTimeZone.value,
    actorIds: [...draftFilters.actorIds],
    modules: [...draftFilters.modules],
    actions: [...draftFilters.actions],
    results: [...draftFilters.results],
  };
}

async function loadRecords(
  pageNumber: number = intRequestedPage,
  reloadOptions: boolean = false,
): Promise<void> {
  const intCurrentRevision = ++intListRevision;
  boolLoading.value = true;
  requestError.value = null;
  intRequestedPage = pageNumber;
  try {
    const [page, options] = await Promise.all([
      getAuditList(appliedFilters, pageNumber),
      reloadOptions || !filterOptions.value ? getAuditFilterOptions() : filterOptions.value,
    ]);
    if (intCurrentRevision !== intListRevision) return;
    recordPage.value = page;
    filterOptions.value = options;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intListRevision) return;
    requestError.value = getApiError(e);
    // Retention cleanup can remove the last page while it is open.
    if (requestError.value.code === "audit_page_not_found" && pageNumber > 1) {
      await loadRecords(1, reloadOptions);
      return;
    }
    if ([401, 403].includes(requestError.value.statusCode)) {
      recordPage.value = null;
      filterOptions.value = null;
      strDetailsId.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intListRevision) boolLoading.value = false;
  }
}

function applyFilters(): void {
  if (boolLoading.value) return;
  appliedFilters = buildFilters();
  recordPage.value = null;
  strUpdatedAt.value = null;
  void loadRecords(1);
}

function resetFilters(): void {
  if (boolLoading.value) return;
  draftFilters.fromDate = "";
  draftFilters.toDate = "";
  draftFilters.actorIds = [];
  draftFilters.modules = [];
  draftFilters.actions = [];
  draftFilters.results = [];
  applyFilters();
}

watch(strTimeZone, (timeZone) => {
  if (!sessionStore.access?.is_org_admin) return;
  appliedFilters = { ...appliedFilters, timeZone };
  recordPage.value = null;
  strUpdatedAt.value = null;
  void loadRecords(1);
});
onMounted(() => void loadRecords());
onBeforeUnmount(() => {
  intListRevision += 1;
});
</script>

<style scoped></style>
