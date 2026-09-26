<!-- FileName: ExecutorGroupsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2">Executor Groups</h1>
      <p class="text-body-2 text-medium-emphasis">
        Executor groups in your authorized departments.
      </p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolLoading || boolNewGroupOpen"
        @click="openNewGroup">
        New Group
      </v-btn>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolNewGroupOpen"
        @click="loadGroups()">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-tabs model-value="groups" color="primary" class="mb-4" aria-label="Executor sections">
    <v-tab value="executors" to="/executors" exact>Executors</v-tab>
    <v-tab value="groups" to="/executors/groups">Executor Groups</v-tab>
  </v-tabs>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form aria-label="Executor group filters" @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="strName"
              label="Name"
              placeholder="Search by name"
              maxlength="128"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="arrDepartmentId"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              placeholder="All accessible departments"
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
  <template v-if="creationResult">
    <v-alert type="success" variant="tonal" class="mb-4" role="status">
      Group "{{ creationResult.executor_group.name }}" created with
      {{ creationResult.executor_group.member_count }} members.
    </v-alert>
    <v-alert
      v-for="warning in creationResult.warnings"
      :key="warning.code"
      type="warning"
      variant="tonal"
      class="mb-4"
      role="status">
      {{ warning.message }}
    </v-alert>
  </template>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="groupPage" class="mt-2">
      Previously loaded results are shown. Refresh to try again.
    </p>
  </v-alert>
  <v-alert
    v-if="
      sessionStore.access &&
      !sessionStore.access.is_org_admin &&
      !sessionStore.access.departments.length
    "
    type="info"
    variant="tonal"
    class="mb-4">
    No department access. Ask an organization administrator to assign a role.
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
      :items="groupPage?.executor_groups ?? []"
      :items-length="groupPage?.total_count ?? 0"
      :items-per-page="groupPage?.page_size ?? 50"
      :page="groupPage?.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading executor groups…"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <div class="group-text font-weight-medium">{{ item.name }}</div>
      </template>
      <template #item.department="{ item }">
        <div class="group-text">{{ item.department.path }}</div>
      </template>
      <template #item.notes="{ item }">
        <div class="group-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>
      <template #no-data>
        {{
          requestError
            ? "The executor group list could not be loaded."
            : "No executor groups match the current filters."
        }}
      </template>
    </v-data-table-server>
    <template v-if="groupPage">
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ groupPage.total_count }} groups · Page {{ groupPage.page }} of
          {{ groupPage.total_pages }}
        </p>
        <v-pagination
          v-if="groupPage.total_pages > 1"
          :model-value="groupPage.page"
          :length="groupPage.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          density="comfortable"
          aria-label="Executor group pages"
          @update:model-value="loadGroups" />
      </div>
    </template>
  </v-card>
  <NewExecutorGroupDialog
    v-if="boolNewGroupOpen"
    :departments="arrCreationDepartment"
    @close="boolNewGroupOpen = false"
    @created="handleGroupCreated" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

import NewExecutorGroupDialog from "../components/NewExecutorGroupDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { type ExecutorGroupListFilters, getExecutorGroupList } from "../api/executorGroups";
import type {
  ExecutorGroupListResponse,
  ExecutorGroupWriteResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 180 },
  { title: "Department", key: "department", minWidth: 180 },
  { title: "Members", key: "member_count", minWidth: 100 },
  { title: "Online", key: "online_count", minWidth: 100 },
  { title: "Notes", key: "notes", minWidth: 240 },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const strName = ref<string | null>("");
const arrDepartmentId = ref<string[]>([]);
const groupPage = shallowRef<ExecutorGroupListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strUpdatedAt = ref<string | null>(null);
const arrCreationDepartment = computed(() =>
  (sessionStore.access?.departments ?? []).filter(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);
const boolCanCreate = computed(
  () => sessionStore.access?.is_org_admin || arrCreationDepartment.value.length > 0,
);
const boolNewGroupOpen = ref(false);
const creationResult = shallowRef<ExecutorGroupWriteResponse | null>(null);
let boolUnmounted = false;
let appliedFilters: ExecutorGroupListFilters = { name: "", departmentIds: [] };
let intRequestedPage = 1;

// TODO: Add URL-based group details and editing/deletion actions in the next group maintenance step.
async function loadGroups(pageNumber: number = intRequestedPage): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  requestError.value = null;
  intRequestedPage = pageNumber;
  try {
    const response = await getExecutorGroupList(appliedFilters, pageNumber);
    if (boolUnmounted) return;
    groupPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403].includes(requestError.value.statusCode)) {
      groupPage.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function applyFilters(): void {
  if (boolLoading.value) return;
  appliedFilters = {
    name: (strName.value ?? "").trim(),
    departmentIds: [...arrDepartmentId.value],
  };
  void loadGroups(1);
}

function resetFilters(): void {
  if (boolLoading.value) return;
  strName.value = "";
  arrDepartmentId.value = [];
  applyFilters();
}

function openNewGroup(): void {
  if (!boolCanCreate.value || boolLoading.value || boolNewGroupOpen.value) return;
  creationResult.value = null;
  boolNewGroupOpen.value = true;
}

function handleGroupCreated(response: ExecutorGroupWriteResponse): void {
  boolNewGroupOpen.value = false;
  creationResult.value = response;
  void loadGroups();
}

onMounted(() => void loadGroups());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped>
.group-text {
  max-width: 360px;
  overflow-wrap: anywhere;
}

.notes-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: pre-line;
}
</style>
