<!-- FileName: DataQueuesView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col><h1 class="text-h5">Data Queues</h1></v-col>
    <v-col cols="auto" class="d-flex ga-2"
      ><v-btn
        v-if="canCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="loading"
        @click="form = 'new'"
        >New Queue</v-btn
      ><v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="loading"
        :disabled="loading"
        @click="load"
        >Refresh</v-btn
      ></v-col
    >
  </v-row>
  <v-card variant="outlined" class="mb-4"
    ><v-card-text
      ><form @submit.prevent="applyFilters">
        <v-row
          ><v-col cols="12" md="6"
            ><v-text-field
              v-model="name"
              label="Name"
              maxlength="128"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              :disabled="loading" /></v-col
          ><v-col cols="12" md="6"
            ><v-autocomplete
              v-model="departments"
              :items="session.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              hide-details
              :disabled="loading" /></v-col
        ></v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal" :disabled="loading"
            >Apply</v-btn
          ><v-btn variant="outlined" :disabled="loading" @click="clearFilters"
            >Clear Filters</v-btn
          >
        </div>
      </form></v-card-text
    ></v-card
  >
  <v-alert v-if="message" type="success" variant="tonal" class="mb-4" role="status"
    >{{ message }}
    <RouterLink v-if="savedQueue" :to="detailsLocation(savedQueue.id)"
      >View</RouterLink
    ></v-alert
  >
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert"
    >{{ error.message }}
    <p v-if="page">Previously loaded results are shown. Refresh to try again.</p></v-alert
  >
  <v-card variant="outlined">
    <v-data-table-server
      :headers="headers"
      :items="page?.queues ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :page="page?.page ?? 1"
      :loading="loading"
      item-value="id"
      disable-sort
      hide-default-footer
      :mobile-breakpoint="600">
      <template #item.name="{ item }"
        ><RouterLink
          :to="detailsLocation(item.id)"
          class="table-text-narrow text-primary"
          >{{ item.name }}</RouterLink
        ></template
      >
      <template #item.department="{ item }"
        ><div class="table-text-narrow">{{ item.department.path }}</div></template
      >
      <template #item.notes="{ item }"
        ><div class="table-text notes-summary">{{ item.notes || "—" }}</div></template
      >
      <template #item.actions="{ item }"
        ><div class="d-flex ga-1">
          <v-btn :to="detailsLocation(item.id)" variant="text" size="small">View</v-btn
          ><v-btn variant="text" size="small" @click="copyPath(item.path)">Copy Path</v-btn
          ><v-btn
            v-if="item.can_manage"
            variant="text"
            size="small"
            :disabled="loading || !!error"
            @click="form = item"
            >Edit</v-btn
          >
        </div></template
      >
      <template #no-data>{{
        error
          ? "The queue list could not be loaded."
          : "No queues match the current filters."
      }}</template>
    </v-data-table-server>
    <div v-if="page" class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
      <p>{{ page.total_count }} queues · Page {{ page.page }} of {{ page.total_pages }}</p>
      <v-pagination
        v-if="page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="loading"
        @update:model-value="changePage" />
    </div>
  </v-card>
  <QueueFormDialog
    v-if="form"
    :queue="form === 'new' ? undefined : form"
    :initial-department-id="departments.length === 1 ? departments[0] : undefined"
    @close="form = null"
    @saved="handleSaved" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink, useRoute, useRouter, type RouteLocationRaw } from "vue-router";

import QueueFormDialog from "../components/QueueFormDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { ApiError, getApiError } from "../api/errors";
import { getQueues } from "../api/dataQueues";
import type {
  QueueListResponse,
  QueueEntryResponse,
  QueueDetailsResponse,
} from "../api/generated/browserApi";

const headers = [
  { title: "Name", key: "name", minWidth: 160 },
  { title: "Department", key: "department", minWidth: 160 },
  { title: "Unclaimed", key: "unclaimed_count" },
  { title: "Claimed", key: "claimed_count" },
  { title: "Notes", key: "notes", minWidth: 220 },
  { title: "Actions", key: "actions", minWidth: 240 },
];
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const canCreate = computed(
  () =>
    session.access?.business_available &&
    session.access.departments.some(
      (department) => session.access?.is_org_admin || department.role === "developer",
    ),
);
const name = ref("");
const departments = ref<string[]>([]);
const page = shallowRef<QueueListResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const form = shallowRef<QueueEntryResponse | "new" | null>(null);
const savedQueue = shallowRef<QueueEntryResponse | null>(null);
const message = ref("");
const loading = ref(false);
let revision = 0;
const detailsLocation = (queueId: string): RouteLocationRaw => ({
  name: "data-queue-details",
  params: { queueId },
  query: route.query,
});
function selectedDepartments(): string[] {
  const value = route.query.department_id;
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string")
    : typeof value === "string"
      ? [value]
      : [];
}
async function load(): Promise<void> {
  const current = ++revision;
  loading.value = true;
  error.value = null;
  try {
    const result = await getQueues(
      typeof route.query.name === "string" ? route.query.name : "",
      selectedDepartments(),
      Number(route.query.page) || 1,
    );
    if (current === revision) page.value = result;
  } catch (e) {
    if (current !== revision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403].includes(error.value.statusCode)) {
      page.value = null;
      form.value = null;
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    if (current === revision) loading.value = false;
  }
}
async function applyFilters(): Promise<void> {
  const query = {
    name: name.value?.trim() || undefined,
    department_id: departments.value,
    page: undefined,
  };
  const target = router.resolve({ name: "data-queues", query });
  if (target.fullPath === route.fullPath) await load();
  else await router.replace({ name: "data-queues", query });
}
function clearFilters(): void {
  name.value = "";
  departments.value = [];
  void applyFilters();
}
async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}
function handleSaved(response: QueueDetailsResponse): void {
  form.value = null;
  savedQueue.value = response.queue;
  message.value = `Queue saved: ${response.queue.path}`;
  void load();
}
async function copyPath(value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value);
    savedQueue.value = null;
    message.value = "Path copied.";
  } catch {
    error.value = new ApiError(
      "The path could not be copied. Open Queue Details to copy it manually.",
    );
  }
}
watch(
  () => [route.query.name, route.query.department_id, route.query.page],
  () => {
    name.value = typeof route.query.name === "string" ? route.query.name : "";
    departments.value = selectedDepartments();
    void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  revision += 1;
});
</script>

<style scoped></style>
