<!-- FileName: AssetsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2">Assets</h1>
      <p class="text-medium-emphasis">Shared values in your authorized departments.</p>
    </v-col>

    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading || boolNewAssetOpen"
        @click="loadAssets()">
        Refresh
      </v-btn>

      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolLoading || boolNewAssetOpen"
        @click="boolNewAssetOpen = true">
        New Asset
      </v-btn>
    </v-col>
  </v-row>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form aria-label="Asset filters" @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" md="4">
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

          <v-col cols="12" md="4">
            <v-select
              v-model="arrDepartmentId"
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

          <v-col cols="12" md="4">
            <v-select
              v-model="arrAssetType"
              :items="ARR_ASSET_TYPE"
              label="Type"
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

  <v-alert
    v-if="strSuccessMessage"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    {{ strSuccessMessage }}
  </v-alert>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="assetPage" class="mt-2">
      Previously loaded results are shown. Refresh to try again.
    </p>
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

  <v-alert
    v-if="!sessionStore.access?.departments.length"
    type="info"
    variant="tonal"
    class="mb-4">
    No department access. Ask an organization administrator to check departments and your
    access.
  </v-alert>

  <TimeZoneHint :time-zone="strTimeZone" :updated-at="strUpdatedAt" />

  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="assetPage?.assets ?? []"
      :items-length="assetPage?.total_count ?? 0"
      :items-per-page="assetPage?.page_size ?? INT_LIST_PAGE_SIZE"
      :page="assetPage?.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <span class="d-inline-block table-text-narrow">
          {{ item.name }}
        </span>
      </template>

      <template #item.department="{ item }">
        <div class="table-text-narrow">{{ item.department.path }}</div>
      </template>

      <template #item.asset_type="{ item }">
        <v-chip
          :color="ASSET_TYPE_COLORS[item.asset_type][strAssetTheme]"
          size="small"
          variant="tonal">
          {{ getAssetTypeLabel(item.asset_type) }}
        </v-chip>
      </template>

      <template #item.value_summary="{ item }">
        <div class="table-text notes-summary">{{ item.value_summary }}</div>
      </template>

      <template #item.notes="{ item }">
        <div class="table-text notes-summary">{{ item.notes || "—" }}</div>
      </template>

      <template #item.updated_at="{ item }">
        <span class="text-no-wrap">
          {{ formatDateTime(item.updated_at, strTimeZone, false) }}
        </span>
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
            v-if="item.can_manage || item.can_edit_value"
            v-tooltip:bottom="'Edit'"
            variant="text"
            size="small"
            aria-label="Edit"
            icon="mdi-pencil-outline"
            :loading="strLoadingAssetId === item.id"
            :disabled="boolLoading || !!strLoadingAssetId"
            @click="openEdit(item.id)" />

          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Delete'"
            variant="text"
            size="small"
            aria-label="Delete"
            icon="mdi-delete-outline"
            :disabled="boolLoading || !!strLoadingAssetId"
            @click="strDeleteAssetId = item.id" />
        </div>
      </template>

      <template #no-data>
        {{
          requestError
            ? "The asset list could not be loaded."
            : "No assets match the current filters."
        }}
      </template>
    </v-data-table-server>

    <template v-if="assetPage">
      <v-divider />

      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ assetPage.total_count }} assets · Page {{ assetPage.page }} of
          {{ assetPage.total_pages }}
        </p>

        <v-pagination
          v-if="assetPage.total_pages > 1"
          :model-value="assetPage.page"
          :length="assetPage.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          density="comfortable"
          aria-label="Asset pages"
          @update:model-value="loadAssets" />
      </div>
    </template>
  </v-card>

  <AssetFormDialog
    v-if="boolNewAssetOpen"
    mode="create"
    @close="boolNewAssetOpen = false"
    @saved="handleCreated" />

  <AssetFormDialog
    v-if="assetEdit"
    :key="assetEdit.id"
    mode="edit"
    :asset="assetEdit"
    @close="assetEdit = null"
    @saved="handleSaved" />

  <AssetDeleteDialog
    v-if="strDeleteAssetId"
    :asset-id="strDeleteAssetId"
    @close="strDeleteAssetId = null"
    @deleted="handleDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute } from "vue-router";
import { useTheme } from "vuetify";

import TimeZoneHint from "@/components/common/TimeZoneHint.vue";
import AssetFormDialog from "@/components/assets/AssetFormDialog.vue";
import AssetDeleteDialog from "@/components/assets/AssetDeleteDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  ARR_ASSET_TYPE,
  type AssetListFilters,
  getAssetTypeLabel,
  getAssetList,
  getAssetDetails,
} from "@/api/assets";
import {
  INT_LIST_PAGE_SIZE,
  type AssetType,
  type AssetListResponse,
  type AssetDetailsResponse,
  type AssetDetailsEntryResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const ASSET_TYPE_COLORS: Record<AssetType, { light: string; dark: string }> = {
  text: { light: "blue-grey-darken-3", dark: "blue-grey-lighten-3" },
  integer: { light: "blue-darken-3", dark: "blue-lighten-3" },
  number: { light: "teal-darken-3", dark: "teal-lighten-3" },
  boolean: { light: "green-darken-4", dark: "green-lighten-3" },
  json: { light: "deep-purple-darken-3", dark: "deep-purple-lighten-3" },
  secret_text: { light: "brown-darken-3", dark: "brown-lighten-3" },
  credential: { light: "indigo-darken-3", dark: "indigo-lighten-3" },
};

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 160 },
  { title: "Department", key: "department", minWidth: 160 },
  { title: "Type", key: "asset_type", minWidth: 120 },
  { title: "Value", key: "value_summary", minWidth: 220 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: "Updated At", key: "updated_at", minWidth: 200 },
  { title: "Actions", key: "actions", width: 152 },
];

const sessionStore = useSessionStore();
const route = useRoute();
const theme = useTheme();
const strAssetTheme = computed(() => (theme.current.value.dark ? "dark" : "light"));
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const arrRouteDepartmentId = computed(() => {
  const value = route.query.department_id;
  return (Array.isArray(value) ? value : [value]).filter(
    (id): id is string => typeof id === "string" && id !== "",
  );
});

const boolCanCreate = computed(() =>
  (sessionStore.access?.departments ?? []).some(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);

const strName = ref<string | null>("");

const arrDepartmentId = ref<string[]>([...arrRouteDepartmentId.value]);

const arrAssetType = ref<AssetType[]>([]);
const assetPage = shallowRef<AssetListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolNewAssetOpen = ref(false);
const assetEdit = shallowRef<AssetDetailsEntryResponse | null>(null);
const strDeleteAssetId = ref<string | null>(null);
const strLoadingAssetId = ref<string | null>(null);
let intEditRevision = 0;
const strUpdatedAt = ref<string | null>(null);
const strSuccessMessage = ref("");
const strActionError = ref("");
let intListRevision = 0;
let intRequestedPage = 1;

let appliedFilters: AssetListFilters = {
  name: "",
  departmentIds: [...arrDepartmentId.value],
  assetTypes: [],
};

async function loadAssets(pageNumber: number = intRequestedPage): Promise<void> {
  const intCurrentRevision = ++intListRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  strActionError.value = "";
  try {
    const response = await getAssetList(appliedFilters, pageNumber);
    if (intCurrentRevision !== intListRevision) return;
    assetPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intListRevision) return;
    requestError.value = getApiError(e);
    if (requestError.value.code === "invalid_page" && pageNumber > 1) {
      await loadAssets(1);
      return;
    }
    if ([401, 403].includes(requestError.value.statusCode)) {
      assetPage.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intListRevision) boolLoading.value = false;
  }
}

function applyFilters(): void {
  appliedFilters = {
    name: (strName.value ?? "").trim(),
    departmentIds: [...arrDepartmentId.value],
    assetTypes: [...arrAssetType.value],
  };
  void loadAssets(1);
}

function clearFilters(): void {
  strName.value = "";
  arrDepartmentId.value = [];
  arrAssetType.value = [];
  applyFilters();
}

function handleCreated(response: AssetDetailsResponse): void {
  boolNewAssetOpen.value = false;
  strSuccessMessage.value = `Asset "${response.asset.name}" created.`;
  void loadAssets();
}

async function openEdit(assetId: string): Promise<void> {
  if (strLoadingAssetId.value) return;
  const intRevision = ++intEditRevision;
  strLoadingAssetId.value = assetId;
  strActionError.value = "";
  try {
    const response = await getAssetDetails(assetId);
    if (intRevision === intEditRevision) assetEdit.value = response.asset;
  } catch (e) {
    if (intRevision === intEditRevision) strActionError.value = getApiError(e).message;
  } finally {
    if (intRevision === intEditRevision) strLoadingAssetId.value = null;
  }
}

function handleSaved(): void {
  assetEdit.value = null;
  strSuccessMessage.value = "Asset updated.";
  void loadAssets();
}

function handleDeleted(): void {
  strDeleteAssetId.value = null;
  strSuccessMessage.value = "Asset deleted.";
  void loadAssets();
}

async function copyPath(path: string): Promise<void> {
  const intCurrentRevision = intListRevision;
  strActionError.value = "";
  strSuccessMessage.value = "";
  try {
    await navigator.clipboard.writeText(path);
    if (intCurrentRevision === intListRevision) strSuccessMessage.value = "Path copied.";
  } catch {
    if (intCurrentRevision === intListRevision)
      strActionError.value = "The path could not be copied.";
  }
}

watch(arrRouteDepartmentId, (departmentIds, previousDepartmentIds) => {
  if (
    departmentIds.length === previousDepartmentIds.length &&
    departmentIds.every((id, index) => id === previousDepartmentIds[index])
  )
    return;

  arrDepartmentId.value = [...departmentIds];
  appliedFilters = { ...appliedFilters, departmentIds: [...departmentIds] };
  assetPage.value = null;
  strUpdatedAt.value = null;
  void loadAssets(1);
});

onMounted(() => void loadAssets());

onBeforeUnmount(() => {
  intListRevision += 1;
  intEditRevision += 1;
});
</script>

<style scoped></style>
