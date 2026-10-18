<!-- FileName: SharedFilesView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5">Shared Files</h1>
    </v-col>

    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="load">
        Refresh
      </v-btn>

      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-upload"
        :disabled="!boolReady || !departments.length"
        @click="boolShowUpload = true">
        Upload File
      </v-btn>

      <v-btn
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="!boolReady || !selectedFilePaths.length"
        @click="deletePaths = [...selectedFilePaths]">
        Delete Selected
      </v-btn>
    </v-col>
  </v-row>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="3">
            <v-autocomplete
              v-model="strDepartmentPath"
              :items="departments"
              item-title="path"
              item-value="path"
              label="Department"
              variant="underlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="strName"
              label="File Name"
              maxlength="128"
              variant="underlined"
              density="compact"
              hide-details
              clearable
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-select
              v-model="strSortBy"
              :items="ARR_SORT_OPTION"
              label="Sort By"
              variant="underlined"
              density="compact"
              hide-details
              :disabled="boolLoading" />
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-switch
              v-model="strOrder"
              :label="strOrder === 'desc' ? 'Descending' : 'Ascending'"
              :aria-label="strOrder === 'desc' ? 'Order: Descending' : 'Order: Ascending'"
              true-value="desc"
              false-value="asc"
              true-icon="mdi-sort-descending"
              false-icon="mdi-sort-ascending"
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

  <v-alert
    v-if="strMessage"
    type="success"
    variant="tonal"
    class="mb-4 text-anywhere"
    role="status">
    {{ strMessage }}
  </v-alert>

  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
    {{ error.message }}
  </v-alert>

  <v-alert
    v-if="strActionError"
    type="error"
    variant="tonal"
    closable
    class="mb-4 text-anywhere"
    role="alert"
    @click:close="strActionError = ''">
    {{ strActionError }}
  </v-alert>

  <div v-if="page" class="mb-4">
    <p v-if="page.department_path" class="text-anywhere mb-1">
      {{ page.department_path }}
    </p>

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
      v-model="selectedFilePaths"
      :headers="ARR_HEADER"
      :items="page?.files ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :page="page?.page ?? 1"
      :loading="boolLoading"
      item-value="path"
      :show-select="boolReady"
      disable-sort
      hide-default-footer
      :mobile-breakpoint="600">
      <template #item.department_path="{ item }">
        <span class="text-anywhere">{{ item.department_path }}</span>
      </template>

      <template #item.name="{ item }">
        <span class="text-anywhere">{{ item.name }}</span>
      </template>

      <template #item.size_bytes="{ item }">
        {{ formatFileSize(item.size_bytes) }}
      </template>

      <template #item.uploaded_by_name="{ item }">
        <span class="text-anywhere">{{ item.uploaded_by_name }}</span>
      </template>

      <template #item.uploaded_at="{ item }">
        {{ formatDateTime(item.uploaded_at, strTimeZone) }}
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="
              `Download. If an external download manager fails, use your browser's built-in downloader.`
            "
            variant="text"
            size="small"
            :loading="setDownloadingFilePath.has(item.path)"
            :disabled="!boolReady || setDownloadingFilePath.has(item.path)"
            aria-label="Download"
            icon="mdi-download"
            @click="download(item.path)" />

          <v-btn
            v-tooltip:bottom="'Copy Path'"
            variant="text"
            size="small"
            aria-label="Copy Path"
            icon="mdi-content-copy"
            @click="copyPath(item.path)" />

          <v-btn
            v-tooltip:bottom="'Delete'"
            variant="text"
            size="small"
            color="error"
            :disabled="!boolReady"
            aria-label="Delete"
            icon="mdi-delete-outline"
            @click="deletePaths = [item.path]" />
        </div>
      </template>

      <template #no-data>
        {{
          error
            ? "The file list could not be loaded."
            : "No files match the current filters."
        }}
      </template>
    </v-data-table-server>

    <div v-if="page" class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
      <p>{{ page.total_count }} files · Page {{ page.page }} of {{ page.total_pages }}</p>

      <v-pagination
        v-if="page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading || boolDirty"
        @update:model-value="changePage" />
    </div>
  </v-card>

  <SharedFileUploadDialog
    v-if="boolShowUpload && page"
    :department-path="page.department_path"
    :max-file-bytes="page.usage.max_file_bytes"
    @close="boolShowUpload = false"
    @saved="handleUploaded" />

  <SharedFileDeleteDialog
    v-if="deletePaths"
    :paths="deletePaths"
    @close="deletePaths = null"
    @deleted="handleDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import SharedFileDeleteDialog from "@/components/sharedFiles/SharedFileDeleteDialog.vue";
import SharedFileUploadDialog from "@/components/sharedFiles/SharedFileUploadDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { formatDateTime, formatFileSize } from "@/app/formatters";

import { type ApiError, getApiError } from "@/api/errors";
import { getSharedFiles, downloadSharedFile } from "@/api/sharedFiles";
import type {
  FileDeleteResponse,
  FileInfoResponse,
  FileListRequest,
  FileListResponse,
} from "@/api/generated/browserApi";

const ARR_HEADER = [
  { title: "Department", key: "department_path", minWidth: 180 },
  { title: "File Name", key: "name", minWidth: 180 },
  { title: "Size", key: "size_bytes" },
  { title: "Uploaded By", key: "uploaded_by_name", minWidth: 150 },
  { title: "Uploaded At", key: "uploaded_at", minWidth: 200 },
  { title: "Actions", key: "actions", width: 152 },
];

const ARR_SORT_OPTION = [
  { title: "File Name", value: "name" },
  { title: "Size", value: "size" },
  { title: "Uploaded At", value: "uploaded_at" },
];

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();

const departments = computed(() =>
  (sessionStore.access?.departments ?? []).map((entry) => ({ path: `/${entry.path}` })),
);

const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const strActiveDepartmentPath = computed(() =>
  typeof route.query.department_path === "string" ? route.query.department_path : "",
);

const strActiveName = computed(() =>
  typeof route.query.name === "string" ? route.query.name : "",
);

const strActiveSort = computed<FileListRequest["sort_by"]>(() =>
  route.query.sort_by === "name" || route.query.sort_by === "size"
    ? route.query.sort_by
    : "uploaded_at",
);

const strActiveOrder = computed<FileListRequest["order"]>(() =>
  route.query.order === "asc" ? "asc" : "desc",
);

const strDepartmentPath = ref<string | null>("");
const strName = ref<string | null>("");
const strSortBy = ref<FileListRequest["sort_by"]>("uploaded_at");
const strOrder = ref<FileListRequest["order"]>("desc");
const page = shallowRef<FileListResponse | null>(null);
const selectedFilePaths = ref<string[]>([]);
const error = shallowRef<ApiError | null>(null);
const strMessage = ref("");
const strActionError = ref("");
const boolLoading = ref(false);
const boolShowUpload = ref(false);
const deletePaths = shallowRef<string[] | null>(null);
const setDownloadingFilePath = ref(new Set<string>());

const boolDirty = computed(
  () =>
    (strDepartmentPath.value ?? "") !== strActiveDepartmentPath.value ||
    (strName.value ?? "") !== strActiveName.value ||
    strSortBy.value !== strActiveSort.value ||
    strOrder.value !== strActiveOrder.value,
);

const boolReady = computed(
  () =>
    !!page.value &&
    !boolLoading.value &&
    !error.value &&
    !boolDirty.value &&
    !!sessionStore.access?.business_available,
);

let intRevision = 0;
let boolAlive = true;

async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}

async function load(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  selectedFilePaths.value = [];
  error.value = null;
  strActionError.value = "";
  boolLoading.value = true;
  try {
    const result = await getSharedFiles({
      department_path: strActiveDepartmentPath.value || null,
      name: strActiveName.value,
      sort_by: strActiveSort.value,
      order: strActiveOrder.value,
      page: Number(route.query.page) || 1,
    });
    if (intCurrentRevision === intRevision) page.value = result;
  } catch (e) {
    if (intCurrentRevision !== intRevision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403, 404].includes(error.value.statusCode)) {
      page.value = null;
      boolShowUpload.value = false;
      deletePaths.value = null;
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRevision) boolLoading.value = false;
  }
}

async function applyFilters(): Promise<void> {
  const query = {
    department_path: strDepartmentPath.value || undefined,
    name: strName.value || undefined,
    sort_by: strSortBy.value,
    order: strOrder.value,
  };
  if (router.resolve({ name: "shared-files", query }).fullPath === route.fullPath)
    await load();
  else await router.replace({ name: "shared-files", query });
}

function clearFilters(): void {
  strDepartmentPath.value = "";
  strName.value = "";
  strSortBy.value = "uploaded_at";
  strOrder.value = "desc";
  void applyFilters();
}

function handleUploaded(file: FileInfoResponse): void {
  boolShowUpload.value = false;
  strMessage.value = `File uploaded: ${file.path}`;
  void load();
}

function handleDeleted(result: FileDeleteResponse): void {
  deletePaths.value = null;
  strMessage.value = `${result.deleted_count} ${result.deleted_count === 1 ? "file deleted" : "files deleted"}.${result.missing_paths.length ? ` ${result.missing_paths.length} already unavailable.` : ""}`;
  void load();
}

async function copyPath(path: string): Promise<void> {
  const intCurrentRevision = intRevision;
  strActionError.value = "";
  strMessage.value = "";
  try {
    await navigator.clipboard.writeText(path);
    if (intCurrentRevision === intRevision) strMessage.value = "Path copied.";
  } catch {
    if (intCurrentRevision === intRevision)
      strActionError.value = `Could not copy the path: ${path}`;
  }
}

async function download(path: string): Promise<void> {
  if (setDownloadingFilePath.value.has(path)) return;
  const intCurrentRevision = intRevision;
  strActionError.value = "";
  strMessage.value = "";
  setDownloadingFilePath.value.add(path);
  try {
    await downloadSharedFile(path);
    if (intCurrentRevision === intRevision)
      strMessage.value =
        "Download handed to your browser. Check its downloads for the save status.";
  } catch (e) {
    if (intCurrentRevision === intRevision)
      strActionError.value = `${path}: ${getApiError(e).message}`;
  } finally {
    if (boolAlive) setDownloadingFilePath.value.delete(path);
  }
}

watch([strDepartmentPath, strName, strSortBy, strOrder], () => {
  selectedFilePaths.value = [];
});
// Reload only when the file-list request changes, not for unrelated route changes.
watch(
  [
    strActiveDepartmentPath,
    strActiveName,
    strActiveSort,
    strActiveOrder,
    () => Number(route.query.page) || 1,
  ],
  () => {
    strDepartmentPath.value = strActiveDepartmentPath.value;
    strName.value = strActiveName.value;
    strSortBy.value = strActiveSort.value;
    strOrder.value = strActiveOrder.value;
    page.value = null;
    boolShowUpload.value = false;
    deletePaths.value = null;
    void load();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  boolAlive = false;
  intRevision += 1;
});
</script>

<style scoped></style>
