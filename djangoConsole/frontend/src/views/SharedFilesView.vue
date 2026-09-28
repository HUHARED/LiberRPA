<!-- FileName: SharedFilesView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col><h1 class="text-h5">Shared Files</h1></v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-upload"
        :disabled="!ready"
        @click="showUpload = true"
        >Upload File</v-btn
      >
      <v-btn
        color="error"
        variant="tonal"
        :disabled="!ready || !selected.length"
        @click="deletePaths = [...selected]"
        >Delete Selected</v-btn
      >
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="loading"
        :disabled="loading || !activeDepartment"
        @click="load"
        >Refresh</v-btn
      >
    </v-col>
  </v-row>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="4"
            ><v-autocomplete
              v-model="department"
              :items="departments"
              item-title="path"
              item-value="path"
              label="Department"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              :disabled="loading"
          /></v-col>
          <v-col cols="12" md="4"
            ><v-text-field
              v-model="name"
              label="File Name"
              maxlength="128"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              :disabled="loading"
          /></v-col>
          <v-col cols="6" md="2"
            ><v-select
              v-model="sortBy"
              :items="sortOptions"
              label="Sort By"
              variant="outlined"
              density="compact"
              hide-details
              :disabled="loading"
          /></v-col>
          <v-col cols="6" md="2"
            ><v-select
              v-model="order"
              :items="orderOptions"
              label="Order"
              variant="outlined"
              density="compact"
              hide-details
              :disabled="loading"
          /></v-col>
        </v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal" :disabled="loading"
            >Apply</v-btn
          >
          <v-btn variant="outlined" :disabled="loading" @click="clearFilters"
            >Clear Filters</v-btn
          >
        </div>
      </form>
    </v-card-text>
  </v-card>
  <v-alert
    v-if="message"
    type="success"
    variant="tonal"
    class="mb-4 file-path"
    role="status"
    >{{ message }}</v-alert
  >
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">{{
    error.message
  }}</v-alert>
  <v-alert
    v-if="strActionError"
    type="error"
    variant="tonal"
    closable
    class="mb-4 file-path"
    role="alert"
    @click:close="strActionError = ''">
    {{ strActionError }}
  </v-alert>
  <v-alert v-if="!activeDepartment" type="info" variant="tonal"
    >Select a department to view its files.</v-alert
  >
  <template v-else>
    <div v-if="page" class="mb-4">
      <p class="file-path mb-1">{{ page.department_path }}</p>
      <p class="text-body-2">
        Packages + Files:
        {{ formatFileSize(page.usage.used_bytes + page.usage.reserved_bytes) }} /
        {{ formatFileSize(page.usage.limit_bytes) }} · Maximum
        {{ formatFileSize(page.usage.max_file_bytes) }} per file
      </p>
      <p
        v-if="page.usage.reserved_bytes || page.usage.pending_cleanup_bytes"
        class="text-body-2 text-medium-emphasis">
        Reserved for uploads: {{ formatFileSize(page.usage.reserved_bytes) }} · Awaiting
        cleanup: {{ formatFileSize(page.usage.pending_cleanup_bytes) }}
      </p>
    </div>
    <v-card variant="outlined">
      <v-data-table-server
        v-model="selected"
        :headers="headers"
        :items="page?.files ?? []"
        :items-length="page?.total_count ?? 0"
        :items-per-page="100"
        :page="page?.page ?? 1"
        :loading="loading"
        item-value="path"
        :show-select="ready"
        disable-sort
        hide-default-footer
        :mobile-breakpoint="600">
        <template #item.name="{ item }"
          ><span class="file-path">{{ item.name }}</span></template
        >
        <template #item.size_bytes="{ item }">{{
          formatFileSize(item.size_bytes)
        }}</template>
        <template #item.uploaded_by_name="{ item }"
          ><span class="file-path">{{ item.uploaded_by_name }}</span></template
        >
        <template #item.uploaded_at="{ item }">{{
          formatDateTime(item.uploaded_at, timeZone)
        }}</template>
        <template #item.actions="{ item }">
          <div class="d-flex ga-1">
            <v-btn
              variant="text"
              size="small"
              :loading="downloading.has(item.path)"
              :disabled="!ready || downloading.has(item.path)"
              @click="download(item.path)"
              >Download</v-btn
            >
            <v-btn variant="text" size="small" @click="copyPath(item.path)"
              >Copy Path</v-btn
            >
            <v-btn
              variant="text"
              size="small"
              color="error"
              :disabled="!ready"
              @click="deletePaths = [item.path]"
              >Delete</v-btn
            >
          </div>
        </template>
        <template #no-data>{{
          error
            ? "The file list could not be loaded."
            : "No files match the current filters."
        }}</template>
      </v-data-table-server>
      <div
        v-if="page"
        class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p>{{ page.total_count }} files · Page {{ page.page }} of {{ page.total_pages }}</p>
        <v-pagination
          v-if="page.total_pages > 1"
          :model-value="page.page"
          :length="page.total_pages"
          :total-visible="5"
          :disabled="loading || dirty"
          @update:model-value="changePage" />
      </div>
    </v-card>
  </template>
  <SharedFileUploadDialog
    v-if="showUpload && page"
    :department-path="page.department_path"
    :max-file-bytes="page.usage.max_file_bytes"
    @close="showUpload = false"
    @saved="uploaded" />
  <SharedFileDeleteDialog
    v-if="deletePaths"
    :paths="deletePaths"
    @close="deletePaths = null"
    @deleted="deleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import SharedFileDeleteDialog from "../components/SharedFileDeleteDialog.vue";
import SharedFileUploadDialog from "../components/SharedFileUploadDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { formatDateTime } from "../app/navigation";
import { type ApiError, getApiError } from "../api/errors";
import { downloadSharedFile, formatFileSize, getSharedFiles } from "../api/sharedFiles";
import type {
  FileDeleteResponse,
  FileInfoResponse,
  FileListRequest,
  FileListResponse,
} from "../api/generated/browserApi";

const headers = [
  { title: "File Name", key: "name", minWidth: 180 },
  { title: "Size", key: "size_bytes" },
  { title: "Uploaded By", key: "uploaded_by_name", minWidth: 150 },
  { title: "Uploaded At", key: "uploaded_at", minWidth: 200 },
  { title: "Actions", key: "actions", minWidth: 300 },
];
const sortOptions = [
  { title: "File Name", value: "name" },
  { title: "Size", value: "size" },
  { title: "Uploaded At", value: "uploaded_at" },
];
const orderOptions = [
  { title: "Ascending", value: "asc" },
  { title: "Descending", value: "desc" },
];
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const departments = computed(() =>
  (session.access?.departments ?? []).map((entry) => ({ path: `/${entry.path}` })),
);
const timeZone = computed(() => session.session?.user.time_zone ?? "UTC");
const activeDepartment = computed(() =>
  typeof route.query.department_path === "string"
    ? route.query.department_path
    : departments.value.length === 1
      ? departments.value[0]!.path
      : "",
);
const activeName = computed(() =>
  typeof route.query.name === "string" ? route.query.name : "",
);
const activeSort = computed<FileListRequest["sort_by"]>(() =>
  route.query.sort_by === "name" || route.query.sort_by === "size"
    ? route.query.sort_by
    : "uploaded_at",
);
const activeOrder = computed<FileListRequest["order"]>(() =>
  route.query.order === "asc" ? "asc" : "desc",
);
const department = ref<string | null>("");
const name = ref<string | null>("");
const sortBy = ref<FileListRequest["sort_by"]>("uploaded_at");
const order = ref<FileListRequest["order"]>("desc");
const page = shallowRef<FileListResponse | null>(null);
const selected = ref<string[]>([]);
const error = shallowRef<ApiError | null>(null);
const message = ref("");
const strActionError = ref("");
const loading = ref(false);
const showUpload = ref(false);
const deletePaths = shallowRef<string[] | null>(null);
const downloading = ref(new Set<string>());
const dirty = computed(
  () =>
    (department.value ?? "") !== activeDepartment.value ||
    (name.value ?? "") !== activeName.value ||
    sortBy.value !== activeSort.value ||
    order.value !== activeOrder.value,
);
const ready = computed(
  () =>
    !!page.value &&
    !loading.value &&
    !error.value &&
    !dirty.value &&
    !!session.access?.business_available,
);
let revision = 0;
let alive = true;
async function load(): Promise<void> {
  const current = ++revision;
  selected.value = [];
  error.value = null;
  strActionError.value = "";
  if (!activeDepartment.value) {
    page.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const result = await getSharedFiles({
      department_path: activeDepartment.value,
      name: activeName.value,
      sort_by: activeSort.value,
      order: activeOrder.value,
      page: Number(route.query.page) || 1,
    });
    if (current === revision) page.value = result;
  } catch (e) {
    if (current !== revision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403, 404].includes(error.value.statusCode)) {
      page.value = null;
      showUpload.value = false;
      deletePaths.value = null;
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    if (current === revision) loading.value = false;
  }
}
async function applyFilters(): Promise<void> {
  const query = {
    department_path: department.value || undefined,
    name: name.value || undefined,
    sort_by: sortBy.value,
    order: order.value,
  };
  if (router.resolve({ name: "shared-files", query }).fullPath === route.fullPath)
    await load();
  else await router.replace({ name: "shared-files", query });
}
function clearFilters(): void {
  name.value = "";
  sortBy.value = "uploaded_at";
  order.value = "desc";
  void applyFilters();
}
async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}
function uploaded(file: FileInfoResponse): void {
  showUpload.value = false;
  message.value = `File uploaded: ${file.path}`;
  void load();
}
function deleted(result: FileDeleteResponse): void {
  deletePaths.value = null;
  message.value = `${result.deleted_count} ${result.deleted_count === 1 ? "file deleted" : "files deleted"}.${result.missing_paths.length ? ` ${result.missing_paths.length} already unavailable.` : ""}`;
  void load();
}
async function copyPath(path: string): Promise<void> {
  const current = revision;
  strActionError.value = "";
  message.value = "";
  try {
    await navigator.clipboard.writeText(path);
    if (current === revision) message.value = "Path copied.";
  } catch {
    if (current === revision) strActionError.value = `Could not copy the path: ${path}`;
  }
}
async function download(path: string): Promise<void> {
  if (downloading.value.has(path)) return;
  const current = revision;
  strActionError.value = "";
  message.value = "";
  downloading.value.add(path);
  try {
    await downloadSharedFile(path);
    if (current === revision)
      message.value =
        "Download handed to your browser. Check its downloads for the save status.";
  } catch (e) {
    if (current === revision) strActionError.value = `${path}: ${getApiError(e).message}`;
  } finally {
    if (alive) downloading.value.delete(path);
  }
}

watch([department, name, sortBy, order], () => {
  selected.value = [];
});
// Reload only when the file-list request changes, not for unrelated route changes.
watch(
  [
    activeDepartment,
    activeName,
    activeSort,
    activeOrder,
    () => Number(route.query.page) || 1,
  ],
  () => {
    department.value = activeDepartment.value;
    name.value = activeName.value;
    sortBy.value = activeSort.value;
    order.value = activeOrder.value;
    page.value = null;
    showUpload.value = false;
    deletePaths.value = null;
    void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  alive = false;
  revision += 1;
});
</script>

<style scoped>
.file-path {
  overflow-wrap: anywhere;
}
</style>
