<!-- FileName: EmailView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h1 class="text-h5">Email</h1>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading"
      @click="loadIssues(undefined, true)">
      Refresh
    </v-btn>
  </div>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="issuePage" class="mt-2">
      Previously loaded results are shown and may be out of date.
    </p>
  </v-alert>

  <p v-if="issuePage" class="text-body-2 text-medium-emphasis mb-4">
    Updated at {{ formatDateTime(issuePage.updated_at, issuePage.time_zone) }}
  </p>

  <v-row class="mb-2" aria-label="Instance email usage">
    <v-col cols="12" sm="6" lg="3">
      <h2 class="text-subtitle-1">SMTP Budget</h2>
      <p class="text-h5">
        {{ issuePage?.usage.smtp_budget_used_24h.toLocaleString("en-US") ?? "—" }} /
        {{ issuePage?.usage.smtp_budget_limit_24h.toLocaleString("en-US") ?? "—" }}
      </p>
      <p class="text-body-2 text-medium-emphasis mt-1">Last 24 hours · Used / Limit</p>
    </v-col>

    <v-col cols="12" sm="6" lg="3">
      <h2 class="text-subtitle-1">Run Email Budget</h2>
      <p class="text-h5">
        {{ issuePage?.usage.run_budget_used_24h.toLocaleString("en-US") ?? "—" }} /
        {{ issuePage?.usage.run_budget_limit_24h.toLocaleString("en-US") ?? "—" }}
      </p>
      <p class="text-body-2 text-medium-emphasis mt-1">Last 24 hours · Used / Limit</p>
    </v-col>

    <v-col cols="12" sm="4" lg="2">
      <h2 class="text-subtitle-1">Accepted by SMTP</h2>
      <p class="text-h5">
        {{ issuePage?.usage.accepted_by_smtp_24h.toLocaleString("en-US") ?? "—" }}
      </p>
      <p class="text-body-2 text-medium-emphasis mt-1">Attempts in the last 24 hours</p>
    </v-col>

    <v-col cols="12" sm="4" lg="2">
      <h2 class="text-subtitle-1">Pending</h2>
      <p class="text-h5">
        {{ issuePage?.usage.pending.toLocaleString("en-US") ?? "—" }}
      </p>
      <p class="text-body-2 text-medium-emphasis mt-1">Waiting to be sent</p>
    </v-col>

    <v-col cols="12" sm="4" lg="2">
      <h2 class="text-subtitle-1">Failed Today</h2>
      <p class="text-h5">{{ issuePage?.failed_today.toLocaleString("en-US") ?? "—" }}</p>
      <p v-if="issuePage" class="text-body-2 text-medium-emphasis mt-1">
        {{ issuePage.today }} · {{ issuePage.time_zone }}
      </p>
    </v-col>
  </v-row>

  <p class="text-body-2 text-medium-emphasis mb-1">
    Totals cover all organizations and are not affected by issue filters. Budgets count
    recipient attempts, including failed or unknown results. Run email uses both budgets.
  </p>
  <p class="text-body-2 text-medium-emphasis mb-4">
    SMTP acceptance does not confirm inbox delivery.
  </p>

  <h2 class="text-h6 mb-3">Recent Issues</h2>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form aria-label="Email issue filters" @submit.prevent="applyFilters">
        <p class="text-body-2 text-medium-emphasis mb-4">
          Date filters use {{ strTimeZone }} and include both selected dates.
        </p>

        <v-row>
          <v-col cols="12" sm="6" lg="3">
            <v-text-field
              v-model="draftFilters.fromDate"
              type="date"
              label="From Date"
              variant="underlined"
              density="compact"
              hide-details="auto"
              :error-messages="requestError?.fields.date_from ?? []"
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" sm="6" lg="3">
            <v-text-field
              v-model="draftFilters.toDate"
              type="date"
              label="Through Date"
              variant="underlined"
              density="compact"
              hide-details="auto"
              :error-messages="requestError?.fields.date_to ?? []"
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" sm="6" lg="3">
            <v-autocomplete
              v-model="draftFilters.organizationIds"
              :items="arrOrganizationOption"
              label="Organization"
              placeholder="All organizations"
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

          <v-col cols="12" sm="6" lg="3">
            <v-select
              v-model="draftFilters.statuses"
              :items="filterOptions?.statuses ?? []"
              item-title="label"
              item-value="value"
              label="Status"
              placeholder="All issue statuses"
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

  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="issuePage?.issues ?? []"
      :items-length="issuePage?.pagination.total_count ?? 0"
      :items-per-page="issuePage?.pagination.page_size ?? INT_LIST_PAGE_SIZE"
      :page="issuePage?.pagination.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading email issues…"
      disable-sort
      hide-default-footer>
      <template #item.finished_at="{ item }">
        {{ formatDateTime(item.finished_at, strTimeZone) }}
      </template>

      <template #item.organization_name="{ item }">
        <template v-if="item.organization_id">
          {{ item.organization_name || "Unknown organization" }}
          <p v-if="!item.organization_name" class="text-caption text-medium-emphasis">
            {{ item.organization_id }}
          </p>
        </template>
        <span v-else>—</span>
      </template>

      <template #item.status_label="{ item }">
        <v-chip size="small">{{ item.status_label }}</v-chip>
      </template>

      <template #item.reason_text="{ item }">
        <v-sheet max-width="280" color="transparent" class="text-truncate">
          {{ item.reason_text }}
        </v-sheet>
      </template>

      <template #item.actions="{ item }">
        <v-btn
          v-tooltip:bottom="'View Details'"
          variant="text"
          size="small"
          aria-label="View Details"
          icon="mdi-eye-outline"
          @click="selectedIssue = item" />
      </template>

      <template #no-data>
        {{
          requestError
            ? "The email issues could not be loaded."
            : "No email issues match the current filters."
        }}
      </template>
    </v-data-table-server>

    <template v-if="issuePage">
      <v-divider />

      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ issuePage.pagination.total_count }} issues · Page
          {{ issuePage.pagination.page }} of {{ issuePage.pagination.total_pages }}
        </p>

        <v-pagination
          v-if="issuePage.pagination.total_pages > 1"
          :model-value="issuePage.pagination.page"
          :length="issuePage.pagination.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          aria-label="Email issue pages"
          @update:model-value="loadIssues" />
      </div>
    </template>
  </v-card>

  <v-dialog
    v-if="selectedIssue"
    :model-value="true"
    scrollable
    max-width="850"
    aria-labelledby="email-issue-title"
    @update:model-value="!$event && (selectedIssue = null)">
    <v-card>
      <v-card-title id="email-issue-title">Email Issue Details</v-card-title>

      <v-card-text>
        <v-row>
          <v-col v-for="field in arrDetailField" :key="field.label" cols="12" sm="6">
            <p class="text-caption text-medium-emphasis">{{ field.label }}</p>
            <p class="text-body-2 text-break">{{ field.value }}</p>
          </v-col>
        </v-row>

        <v-divider class="my-4" />

        <p class="text-caption text-medium-emphasis">Reason</p>
        <p class="text-body-2 text-break">{{ selectedIssue.reason_text }}</p>
        <p class="text-caption text-medium-emphasis mt-3">Reason Code</p>
        <p class="text-body-2 text-break">{{ selectedIssue.reason_code || "—" }}</p>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="selectedIssue = null">
          Close
        </v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
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

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  type EmailIssueFilters,
  getEmailIssues,
  getEmailIssueFilters,
} from "@/api/emailIssues";
import {
  INT_LIST_PAGE_SIZE,
  type EmailIssueResponse,
  type EmailIssueListResponse,
  type EmailIssueFiltersResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const ARR_HEADER = [
  { title: "Time", key: "finished_at", minWidth: 180 },
  { title: "Email Type", key: "email_type_label", minWidth: 170 },
  { title: "Organization", key: "organization_name", minWidth: 160 },
  { title: "Recipient", key: "recipient", minWidth: 200 },
  { title: "Status", key: "status_label", minWidth: 110 },
  { title: "Reason", key: "reason_text", minWidth: 220 },
  { title: "Actions", key: "actions", width: 72 },
];

const sessionStore = useSessionStore();
const draftFilters = reactive<EmailIssueFilters>({
  fromDate: "",
  toDate: "",
  organizationIds: [],
  statuses: [],
});

const issuePage = shallowRef<EmailIssueListResponse | null>(null);
const filterOptions = shallowRef<EmailIssueFiltersResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const selectedIssue = shallowRef<EmailIssueResponse | null>(null);
let intRequestedPage = 1;
let intRequestRevision = 0;

const arrOrganizationOption = computed(() => {
  const organizations = filterOptions.value?.organizations ?? [];
  const mapNameCount = new Map<string, number>();
  for (const organization of organizations)
    mapNameCount.set(organization.name, (mapNameCount.get(organization.name) ?? 0) + 1);

  return organizations.map((organization) => ({
    title:
      organization.id === null
        ? "No organization"
        : !organization.name || (mapNameCount.get(organization.name) ?? 0) > 1
          ? `${organization.name || "Unknown organization"} (${organization.id})`
          : organization.name,
    value: organization.id ?? "none",
  }));
});

const arrDetailField = computed(() => {
  const issue = selectedIssue.value;
  if (!issue) return [];
  return [
    { label: "Email Type", value: issue.email_type_label },
    { label: "Status", value: issue.status_label },
    { label: "Recipient", value: issue.recipient },
    {
      label: "Organization",
      value: issue.organization_id
        ? issue.organization_name || "Unknown organization"
        : "—",
    },
    { label: "Organization ID", value: issue.organization_id ?? "—" },
    { label: "Record ID", value: issue.id },
    {
      label: `Created At (${strTimeZone.value})`,
      value: formatDateTime(issue.created_at, strTimeZone.value),
    },
    {
      label: `Attempted At (${strTimeZone.value})`,
      value: formatDateTime(issue.attempted_at, strTimeZone.value),
    },
    {
      label: `Finished At (${strTimeZone.value})`,
      value: formatDateTime(issue.finished_at, strTimeZone.value),
    },
  ];
});

function buildFilters(): EmailIssueFilters {
  return {
    fromDate: draftFilters.fromDate,
    toDate: draftFilters.toDate,
    organizationIds: [...draftFilters.organizationIds],
    statuses: [...draftFilters.statuses],
  };
}

let appliedFilters = buildFilters();

async function loadIssues(
  pageNumber: number = intRequestedPage,
  reloadOptions = false,
): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;

  try {
    const [page, options] = await Promise.all([
      getEmailIssues(appliedFilters, pageNumber),
      reloadOptions || !filterOptions.value ? getEmailIssueFilters() : filterOptions.value,
    ]);
    if (intCurrentRevision !== intRequestRevision) return;
    issuePage.value = page;
    filterOptions.value = options;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    // Retention cleanup can remove the last page while it is open.
    if (requestError.value.code === "email_issue_page_not_found" && pageNumber > 1) {
      await loadIssues(1, reloadOptions);
      return;
    }
    if ([401, 403].includes(requestError.value.statusCode)) {
      issuePage.value = null;
      filterOptions.value = null;
      selectedIssue.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function applyFilters(): void {
  if (boolLoading.value) return;
  appliedFilters = buildFilters();
  issuePage.value = null;
  void loadIssues(1);
}

function resetFilters(): void {
  if (boolLoading.value) return;
  draftFilters.fromDate = "";
  draftFilters.toDate = "";
  draftFilters.organizationIds = [];
  draftFilters.statuses = [];
  applyFilters();
}

watch(strTimeZone, () => {
  issuePage.value = null;
  selectedIssue.value = null;
  void loadIssues(1);
});

onMounted(() => void loadIssues());
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
