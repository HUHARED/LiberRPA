<!-- FileName: ExecutorsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2">Executors</h1>
      <p class="text-medium-emphasis">Executors in your authorized departments.</p>
    </v-col>

    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolLoading || boolNewExecutorOpen"
        @click="openNewExecutor">
        New Executor
      </v-btn>

      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolNewExecutorOpen"
        @click="loadExecutors()">
        Refresh
      </v-btn>
    </v-col>
  </v-row>

  <v-tabs
    model-value="executors"
    color="primary"
    class="mb-4"
    aria-label="Executor sections">
    <v-tab value="executors" to="/executors" exact>Executors</v-tab>
    <v-tab value="groups" to="/executors/groups">Executor Groups</v-tab>
  </v-tabs>

  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form aria-label="Executor filters" @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="4">
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

          <v-col cols="12" md="4">
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

          <v-col cols="12" md="4">
            <v-select
              v-model="arrDispatchState"
              :items="ARR_DISPATCH_OPTION"
              label="Console Dispatch"
              placeholder="All dispatch states"
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

  <v-alert v-if="createdExecutor" type="success" variant="tonal" class="mb-4" role="status">
    Executor created.
    <RouterLink
      :to="{ name: 'executor-details', params: { executorId: createdExecutor.id } }"
      class="text-primary">
      View {{ createdExecutor.name }}
    </RouterLink>
  </v-alert>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="executorPage" class="mt-2">
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
      :items="executorPage?.executors ?? []"
      :items-length="executorPage?.total_count ?? 0"
      :items-per-page="executorPage?.page_size ?? 50"
      :page="executorPage?.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading executors…"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <RouterLink
          :to="{ name: 'executor-details', params: { executorId: item.id } }"
          class="d-inline-block table-text-narrow text-primary">
          {{ item.name }}
        </RouterLink>
      </template>

      <template #item.department="{ item }">
        <div class="table-text-narrow">{{ item.department.path }}</div>
      </template>

      <template #item.account="{ item }">
        <div class="table-text-narrow">
          {{
            item.account
              ? item.account.username
                ? `${item.account.username} (${item.account.email})`
                : item.account.email
              : "—"
          }}
        </div>
      </template>

      <template #item.association_status="{ item }">
        <v-chip
          size="small"
          variant="tonal"
          :color="DICT_ASSOCIATION_STATE[item.association_status].color">
          {{ DICT_ASSOCIATION_STATE[item.association_status].title }}
        </v-chip>
      </template>

      <template #item.dispatch_enabled="{ item }">
        <v-chip
          size="small"
          variant="tonal"
          :color="item.dispatch_enabled ? 'primary' : 'warning'">
          {{ item.dispatch_enabled ? "Enabled" : "Paused" }}
        </v-chip>
      </template>

      <template #item.computer="{ item }">
        <div class="table-text-narrow">{{ item.computer ?? "—" }}</div>
      </template>

      <template #item.version="{ item }">{{ item.version ?? "—" }}</template>

      <template #item.last_seen_at="{ item }">
        {{ formatDateTime(item.last_seen_at, strTimeZone) }}
      </template>

      <template #item.notes="{ item }">
        <div class="table-text-narrow notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>

      <template #no-data>
        {{
          requestError
            ? "The executor list could not be loaded."
            : "No executors match the current filters."
        }}
      </template>
    </v-data-table-server>

    <template v-if="executorPage">
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ executorPage.total_count }} executors · Page {{ executorPage.page }} of
          {{ executorPage.total_pages }}
        </p>

        <v-pagination
          v-if="executorPage.total_pages > 1"
          :model-value="executorPage.page"
          :length="executorPage.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          density="comfortable"
          aria-label="Executor pages"
          @update:model-value="loadExecutors" />
      </div>
    </template>
  </v-card>

  <v-dialog
    v-model="boolNewExecutorOpen"
    persistent
    max-width="640"
    aria-labelledby="executor-create-title">
    <v-card v-if="boolNewExecutorOpen">
      <v-card-title id="executor-create-title">New Executor</v-card-title>
      <v-form validate-on="submit" @submit.prevent="submitNewExecutor">
        <v-card-text>
          <v-alert
            v-if="newExecutorError"
            type="error"
            variant="tonal"
            class="mb-4"
            role="alert">
            Creation was not confirmed. {{ newExecutorError.message }}
            <p
              v-for="message in newExecutorError.fields.__all__"
              :key="message"
              class="mt-2">
              {{ message }}
            </p>
          </v-alert>
          <v-alert
            v-if="!arrCreationDepartment.length"
            type="info"
            variant="tonal"
            class="mb-4">
            No departments are available for creation. Ask an organization administrator to
            check departments and your access.
          </v-alert>
          <v-text-field
            v-model="strNewName"
            label="Name"
            variant="outlined"
            density="compact"
            maxlength="128"
            :rules="[validateNewName]"
            :error-messages="newExecutorError?.fields.name ?? []"
            :disabled="boolSavingNewExecutor"
            required
            @update:model-value="newExecutorError = null" />
          <v-select
            v-model="strNewDepartmentId"
            :items="arrCreationDepartment"
            item-title="path"
            item-value="id"
            label="Department"
            variant="outlined"
            density="compact"
            hint="The department cannot be changed after creation."
            persistent-hint
            :rules="[validateNewDepartment]"
            :error-messages="
              newExecutorError?.fields.department ??
              newExecutorError?.fields.department_id ??
              []
            "
            :disabled="boolSavingNewExecutor"
            required
            class="mb-4"
            @update:model-value="newExecutorError = null" />
          <v-textarea
            v-model="strNewNotes"
            label="Notes"
            variant="outlined"
            rows="4"
            counter="2000"
            maxlength="2000"
            :error-messages="newExecutorError?.fields.notes ?? []"
            :disabled="boolSavingNewExecutor"
            @update:model-value="newExecutorError = null" />
          <p>The new Executor starts Unassociated with Console Dispatch enabled.</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="boolSavingNewExecutor" @click="closeNewExecutor">
            Cancel
          </v-btn>
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            :loading="boolSavingNewExecutor"
            :disabled="boolSavingNewExecutor || !arrCreationDepartment.length">
            Create
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink, useRoute } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import {
  type ExecutorListFilters,
  getExecutorList,
  createExecutor,
} from "../api/executors";
import type {
  ExecutorListResponse,
  ExecutorRecordResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 160 },
  { title: "Department", key: "department", minWidth: 160 },
  { title: "Account", key: "account", minWidth: 220 },
  { title: "Association", key: "association_status", minWidth: 140 },
  { title: "Console Dispatch", key: "dispatch_enabled", minWidth: 170 },
  { title: "Computer", key: "computer", minWidth: 150 },
  { title: "Version", key: "version", minWidth: 100 },
  { title: "Last Seen", key: "last_seen_at", minWidth: 220 },
  { title: "Notes", key: "notes", minWidth: 200 },
];
const ARR_DISPATCH_OPTION = [
  { title: "Enabled", value: true },
  { title: "Paused", value: false },
];
const DICT_ASSOCIATION_STATE = {
  unassociated: { title: "Unassociated", color: "secondary" },
  online: { title: "Online", color: "success" },
  offline: { title: "Offline", color: "warning" },
};

const sessionStore = useSessionStore();
const route = useRoute();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const strName = ref<string | null>("");
const arrDepartmentId = ref<string[]>(
  typeof route.query.department_id === "string" ? [route.query.department_id] : [],
);
const arrDispatchState = ref<boolean[]>([]);
const executorPage = shallowRef<ExecutorListResponse | null>(null);
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
const boolNewExecutorOpen = ref(false);
const boolSavingNewExecutor = ref(false);
const newExecutorError = shallowRef<ApiError | null>(null);
const createdExecutor = shallowRef<ExecutorRecordResponse | null>(null);
const strNewName = ref<string | null>("");
const strNewDepartmentId = ref<string | null>(null);
const strNewNotes = ref<string | null>("");
let boolUnmounted = false;
let appliedFilters: ExecutorListFilters = {
  name: "",
  departmentIds: [...arrDepartmentId.value],
  dispatchStates: [],
};
let intRequestedPage = 1;

async function loadExecutors(pageNumber: number = intRequestedPage): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  requestError.value = null;
  intRequestedPage = pageNumber;
  try {
    const response = await getExecutorList(appliedFilters, pageNumber);
    if (boolUnmounted) return;
    executorPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 401 || requestError.value.statusCode === 403) {
      // Confirmed access failures clear old results; temporary failures retain the last successful list.
      executorPage.value = null;
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
    dispatchStates: [...arrDispatchState.value],
  };
  void loadExecutors(1);
}

function resetFilters(): void {
  if (boolLoading.value) return;
  strName.value = "";
  arrDepartmentId.value = [];
  arrDispatchState.value = [];
  applyFilters();
}

function openNewExecutor(): void {
  if (!boolCanCreate.value || boolLoading.value || boolNewExecutorOpen.value) return;
  strNewName.value = "";
  strNewNotes.value = "";
  strNewDepartmentId.value =
    arrCreationDepartment.value.length === 1 ? arrCreationDepartment.value[0]!.id : null;
  newExecutorError.value = null;
  createdExecutor.value = null;
  boolNewExecutorOpen.value = true;
}

function closeNewExecutor(): void {
  boolNewExecutorOpen.value = false;
  strNewName.value = "";
  strNewDepartmentId.value = null;
  strNewNotes.value = "";
  newExecutorError.value = null;
}

function validateNewName(value: string | null): true | string {
  return value?.trim() ? true : "Enter an executor name.";
}

function validateNewDepartment(value: string | null): true | string {
  return arrCreationDepartment.value.some((department) => department.id === value)
    ? true
    : "Select a department where you can create executors.";
}

async function submitNewExecutor(event: SubmitEventPromise): Promise<void> {
  if (!boolNewExecutorOpen.value || boolSavingNewExecutor.value) return;

  const validationResult = await event;
  if (
    !validationResult.valid ||
    !boolNewExecutorOpen.value ||
    boolSavingNewExecutor.value ||
    boolUnmounted ||
    !strNewDepartmentId.value ||
    validateNewDepartment(strNewDepartmentId.value) !== true
  )
    return;
  boolSavingNewExecutor.value = true;
  newExecutorError.value = null;
  try {
    const response = await createExecutor({
      name: (strNewName.value ?? "").trim(),
      department_id: strNewDepartmentId.value,
      notes: strNewNotes.value ?? "",
    });
    if (boolUnmounted) return;

    closeNewExecutor();
    createdExecutor.value = response.executor;
    // Keep the current filters; the success link also reaches records outside these results.
    await loadExecutors();
  } catch (e) {
    if (boolUnmounted) return;
    newExecutorError.value = getApiError(e);
    if ([403, 404].includes(newExecutorError.value.statusCode))
      await sessionStore.refreshSession();
  } finally {
    boolSavingNewExecutor.value = false;
  }
}

onMounted(() => void loadExecutors());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
