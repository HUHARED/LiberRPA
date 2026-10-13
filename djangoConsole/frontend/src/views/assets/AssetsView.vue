<!-- FileName: AssetsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2">Assets</h1>
      <p class="text-medium-emphasis">Shared values in your authorized departments.</p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolLoading || boolNewAssetOpen"
        @click="boolNewAssetOpen = true">
        New Asset
      </v-btn>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading || boolNewAssetOpen"
        @click="loadAssets()">
        Refresh
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
              v-model="arrAssetType"
              :items="ARR_ASSET_TYPE"
              label="Type"
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
          <v-btn variant="tonal" :disabled="boolLoading" @click="clearFilters">
            Reset Filters
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
      :items="assetPage?.assets ?? []"
      :items-length="assetPage?.total_count ?? 0"
      :items-per-page="assetPage?.page_size ?? 50"
      :page="assetPage?.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <RouterLink
          :to="getDetailsLocation(item.id)"
          class="d-inline-block table-text-narrow text-primary text-decoration-none">
          {{ item.name }}
        </RouterLink>
      </template>
      <template #item.department="{ item }">
        <div class="table-text-narrow">{{ item.department.path }}</div>
      </template>
      <template #item.asset_type="{ item }">
        {{ getAssetTypeLabel(item.asset_type) }}
      </template>
      <template #item.value_summary="{ item }">
        <div class="table-text notes-summary">{{ item.value_summary }}</div>
      </template>
      <template #item.notes="{ item }">
        <div class="table-text notes-summary">{{ item.notes || "—" }}</div>
      </template>
      <template #item.updated_at="{ item }">
        <span class="text-no-wrap">{{ formatDateTime(item.updated_at, strTimeZone) }}</span>
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
  <RouterView v-slot="{ Component }">
    <component
      :is="Component"
      :key="route.path"
      @updated="handleUpdated"
      @deleted="handleDeleted" />
  </RouterView>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import AssetFormDialog from "@/components/assets/AssetFormDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  ARR_ASSET_TYPE,
  type AssetListFilters,
  getAssetTypeLabel,
  getAssetList,
} from "@/api/assets";
import type {
  AssetType,
  AssetListResponse,
  AssetDetailsResponse,
} from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 160 },
  { title: "Department", key: "department", minWidth: 160 },
  { title: "Type", key: "asset_type", minWidth: 120 },
  { title: "Value", key: "value_summary", minWidth: 220 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: "Updated At", key: "updated_at", minWidth: 240 },
  { title: "Actions", key: "actions", width: 72 },
];
const sessionStore = useSessionStore();
const route = useRoute();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolCanCreate = computed(() =>
  (sessionStore.access?.departments ?? []).some(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);
const strName = ref<string | null>("");
const arrDepartmentId = ref<string[]>(
  typeof route.query.department_id === "string" ? [route.query.department_id] : [],
);
const arrAssetType = ref<AssetType[]>([]);
const assetPage = shallowRef<AssetListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolNewAssetOpen = ref(false);
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

function getDetailsLocation(assetId: string): RouteLocationRaw {
  return { name: "asset-details", params: { assetId }, query: route.query };
}

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
function handleUpdated(): void {
  strSuccessMessage.value = "";
  void loadAssets();
}
function handleDeleted(): void {
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
      strActionError.value =
        "The path could not be copied. Open the asset details to copy it manually.";
  }
}

watch(
  () => route.params.assetId,
  (assetId) => {
    if (assetId) boolNewAssetOpen.value = false;
  },
);
onMounted(() => void loadAssets());
onBeforeUnmount(() => {
  intListRevision += 1;
});
</script>

<style scoped></style>
