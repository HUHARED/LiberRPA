<!-- FileName: DataQueuesView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5">Data Queues</h1>
    </v-col>

    <v-col cols="auto" class="d-flex ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="load">
        Refresh
      </v-btn>

      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolLoading"
        @click="form = 'new'">
        New Queue
      </v-btn>
    </v-col>
  </v-row>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="strName"
              label="Name"
              maxlength="128"
              variant="underlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" md="6">
            <v-autocomplete
              v-model="departmentIds"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
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
            @click="clearFilters">
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

  <v-alert v-if="strMessage" type="success" variant="tonal" class="mb-4" role="status">
    {{ strMessage }}
    <RouterLink
      v-if="savedQueue"
      :to="getDetailsLocation(savedQueue.id)"
      class="text-primary text-decoration-none">
      View
    </RouterLink>
  </v-alert>

  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
    {{ error.message }}
    <p v-if="page">Previously loaded results are shown. Refresh to try again.</p>
  </v-alert>

  <v-alert
    v-if="strActionError"
    type="error"
    variant="tonal"
    closable
    class="mb-4"
    role="alert"
    @click:close="strActionError = ''">
    {{ strActionError }}
  </v-alert>

  <v-card variant="outlined">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="page?.queues ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :page="page?.page ?? 1"
      :loading="boolLoading"
      item-value="id"
      disable-sort
      hide-default-footer
      :mobile-breakpoint="600">
      <template #item.name="{ item }">
        <RouterLink
          :to="getDetailsLocation(item.id)"
          class="table-text-narrow text-primary text-decoration-none">
          {{ item.name }}
        </RouterLink>
      </template>

      <template #item.department="{ item }">
        <div class="table-text-narrow">{{ item.department.path }}</div>
      </template>

      <template #item.notes="{ item }">
        <div class="table-text notes-summary">{{ item.notes || "—" }}</div>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="'Copy Path'"
            variant="text"
            size="small"
            aria-label="Copy Path"
            icon="mdi-content-copy"
            @click="copyPath(item.path)" />

          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Edit'"
            variant="text"
            size="small"
            :disabled="boolLoading || !!error"
            aria-label="Edit"
            icon="mdi-pencil-outline"
            @click="form = item" />

          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Delete'"
            color="error"
            variant="text"
            size="small"
            :disabled="boolLoading || !!error"
            aria-label="Delete"
            icon="mdi-delete-outline"
            @click="deleteTarget = item" />
        </div>
      </template>

      <template #no-data>
        {{
          error
            ? "The queue list could not be loaded."
            : "No queues match the current filters."
        }}
      </template>
    </v-data-table-server>

    <div v-if="page" class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
      <p>{{ page.total_count }} queues · Page {{ page.page }} of {{ page.total_pages }}</p>

      <v-pagination
        v-if="page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="changePage" />
    </div>
  </v-card>

  <QueueFormDialog
    v-if="form"
    :queue="form === 'new' ? undefined : form"
    :initial-department-id="departmentIds.length === 1 ? departmentIds[0] : undefined"
    @close="form = null"
    @saved="handleSaved" />

  <QueueDeleteDialog
    v-if="deleteTarget"
    :queue="deleteTarget"
    @close="deleteTarget = null"
    @deleted="handleDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink, useRoute, useRouter, type RouteLocationRaw } from "vue-router";

import QueueFormDialog from "@/components/dataQueues/QueueFormDialog.vue";
import QueueDeleteDialog from "@/components/dataQueues/QueueDeleteDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getQueues } from "@/api/dataQueues";
import type {
  QueueListResponse,
  QueueEntryResponse,
  QueueDetailsResponse,
} from "@/api/generated/browserApi";

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 160 },
  { title: "Department", key: "department", minWidth: 160 },
  { title: "Unclaimed", key: "unclaimed_count" },
  { title: "Claimed", key: "claimed_count" },
  { title: "Notes", key: "notes", minWidth: 220 },
  { title: "Actions", key: "actions", width: 160 },
];

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();

const boolCanCreate = computed(
  () =>
    sessionStore.access?.business_available &&
    sessionStore.access.departments.some(
      (department) => sessionStore.access?.is_org_admin || department.role === "developer",
    ),
);

const strName = ref("");
const departmentIds = ref<string[]>([]);
const page = shallowRef<QueueListResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const form = shallowRef<QueueEntryResponse | "new" | null>(null);
const deleteTarget = shallowRef<QueueEntryResponse | null>(null);
const savedQueue = shallowRef<QueueEntryResponse | null>(null);
const strMessage = ref("");
const strActionError = ref("");
const boolLoading = ref(false);
let intRevision = 0;

const getDetailsLocation = (queueId: string): RouteLocationRaw => ({
  name: "data-queue-details",
  params: { queueId },
  query: route.query,
});

function getSelectedDepartmentIds(): string[] {
  const value = route.query.department_id;
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string")
    : typeof value === "string"
      ? [value]
      : [];
}

async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}

async function load(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  boolLoading.value = true;
  error.value = null;
  strActionError.value = "";
  try {
    const result = await getQueues(
      typeof route.query.name === "string" ? route.query.name : "",
      getSelectedDepartmentIds(),
      Number(route.query.page) || 1,
    );
    if (intCurrentRevision === intRevision) page.value = result;
  } catch (e) {
    if (intCurrentRevision !== intRevision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403].includes(error.value.statusCode)) {
      page.value = null;
      form.value = null;
      deleteTarget.value = null;
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRevision) boolLoading.value = false;
  }
}

async function applyFilters(): Promise<void> {
  const query = {
    name: strName.value?.trim() || undefined,
    department_id: departmentIds.value,
    page: undefined,
  };
  const target = router.resolve({ name: "data-queues", query });
  if (target.fullPath === route.fullPath) await load();
  else await router.replace({ name: "data-queues", query });
}

function clearFilters(): void {
  strName.value = "";
  departmentIds.value = [];
  void applyFilters();
}

function handleSaved(response: QueueDetailsResponse): void {
  form.value = null;
  savedQueue.value = response.queue;
  strMessage.value = `Queue saved: ${response.queue.path}`;
  void load();
}

function handleDeleted(queue: QueueEntryResponse): void {
  deleteTarget.value = null;
  savedQueue.value = null;
  strMessage.value = `Queue deleted: ${queue.path}`;
  void load();
}

async function copyPath(value: string): Promise<void> {
  const intCurrentRevision = intRevision;
  strActionError.value = "";
  strMessage.value = "";
  savedQueue.value = null;
  try {
    await navigator.clipboard.writeText(value);
    if (intCurrentRevision === intRevision) strMessage.value = "Path copied.";
  } catch {
    if (intCurrentRevision === intRevision)
      strActionError.value =
        "The path could not be copied. Open Queue Details to copy it manually.";
  }
}

watch(
  () => [route.query.name, route.query.department_id, route.query.page],
  () => {
    strName.value = typeof route.query.name === "string" ? route.query.name : "";
    departmentIds.value = getSelectedDepartmentIds();
    void load();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRevision += 1;
});
</script>

<style scoped></style>
