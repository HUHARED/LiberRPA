<!-- FileName: PackagesView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Packages</h1>
    <v-spacer />

    <v-btn
      v-if="boolCanCreate"
      color="primary"
      variant="tonal"
      prepend-icon="mdi-upload"
      @click="boolUpload = true">
      Upload Package
    </v-btn>

    <v-btn variant="tonal" :loading="boolLoading" @click="load">Refresh</v-btn>
  </div>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <div class="package-browser">
    <v-card variant="flat" class="browser-column">
      <v-card-title class="text-subtitle-1">Project Name</v-card-title>

      <v-card-text class="flex-grow-0 pb-2">
        <v-select
          :model-value="arrDepartmentId"
          :items="sessionStore.access?.departments ?? []"
          item-title="path"
          item-value="id"
          label="Department"
          variant="underlined"
          density="compact"
          multiple
          chips
          clearable
          hide-details
          @update:model-value="changeDepartments" />
      </v-card-text>

      <v-divider />

      <v-list class="flex-grow-1 overflow-y-auto" density="compact">
        <v-list-item
          v-for="projectGroup in projectGroupPage?.project_groups ?? []"
          :key="`${projectGroup.department_id}:${projectGroup.project_name_key}`"
          :to="getPackageLocation(projectGroup.latest_package_id)"
          :active="projectGroup === selectedProjectGroup"
          color="primary"
          class="text-decoration-none">
          <template #title>
            <span v-tooltip:bottom="projectGroup.project_name" class="text-primary">
              {{ projectGroup.project_name }}
            </span>
          </template>

          <template #append>
            <v-chip
              v-tooltip:bottom="projectGroup.department_path"
              size="x-small"
              class="department-label ml-2">
              <span class="text-truncate">{{ projectGroup.department_path }}</span>
            </v-chip>
          </template>
        </v-list-item>

        <v-list-item v-if="!boolLoading && !projectGroupPage?.project_groups.length">
          No packages match the selected departments.
        </v-list-item>
      </v-list>

      <v-pagination
        v-if="projectGroupPage && projectGroupPage.total_pages > 1"
        :model-value="projectGroupPage.page"
        :length="projectGroupPage.total_pages"
        :total-visible="1"
        density="compact"
        :disabled="boolLoading"
        @update:model-value="changeProjectGroupPage" />
    </v-card>

    <v-card variant="flat" class="browser-column">
      <v-card-title class="text-subtitle-1">Project Version</v-card-title>

      <v-divider />

      <v-list class="flex-grow-1 overflow-y-auto" density="compact">
        <v-list-item
          v-for="packageEntry in projectPackagePage?.packages ?? []"
          :key="packageEntry.id"
          :to="getPackageLocation(packageEntry.id)"
          :active="packageEntry.id === details?.package.id"
          color="primary"
          class="text-primary text-decoration-none">
          <template #title>
            <span v-tooltip:bottom="packageEntry.project_version">
              {{ packageEntry.project_version }}
            </span>
          </template>
        </v-list-item>
      </v-list>

      <v-pagination
        v-if="projectPackagePage && projectPackagePage.total_pages > 1"
        :model-value="projectPackagePage.page"
        :length="projectPackagePage.total_pages"
        :total-visible="1"
        density="compact"
        :disabled="boolLoading"
        @update:model-value="changeProjectPackagePage" />
    </v-card>

    <v-card variant="flat" class="browser-column">
      <v-card-title class="text-subtitle-1">Package Details</v-card-title>

      <v-divider />
      <v-progress-linear v-if="boolLoading" indeterminate color="primary" />

      <v-card-text class="overflow-y-auto">
        <PackageDetailsPanel
          v-if="details"
          :key="details.package.id"
          :details="details"
          @updated="details = $event"
          @deleted="handleDeleted" />

        <p v-else-if="!boolLoading" class="text-medium-emphasis">
          Select a package to view its details.
        </p>
      </v-card-text>
    </v-card>
  </div>

  <PackageUploadDialog
    v-if="boolUpload"
    @close="boolUpload = false"
    @saved="handleUploaded" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter, type RouteLocationRaw } from "vue-router";

import PackageDetailsPanel from "@/components/packages/PackageDetailsPanel.vue";
import PackageUploadDialog from "@/components/packages/PackageUploadDialog.vue";

import {
  getPackageProjectGroups,
  getProjectPackages,
  getPackageDetails,
  type PackageDetails,
  type PackageInfo,
  type PackageProjectGroupPage,
  type ProjectPackagePage,
} from "@/api/packages";
import { getApiError } from "@/api/errors";

import { useSessionStore } from "@/stores/sessionStore";

defineProps<{ packageId?: string }>();

const sessionStore = useSessionStore();
const router = useRouter();
const route = useRoute();

const boolCanCreate = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some((department) => department.role === "developer"),
);

const arrDepartmentId = computed(() => {
  const value = route.query.department_id;
  return (Array.isArray(value) ? value : [value]).filter(
    (id): id is string => typeof id === "string" && id !== "",
  );
});

const projectGroupPage = shallowRef<PackageProjectGroupPage | null>(null);
const projectPackagePage = shallowRef<ProjectPackagePage | null>(null);
const details = shallowRef<PackageDetails | null>(null);

const selectedProjectGroup = computed(() =>
  projectGroupPage.value?.project_groups.find(
    (projectGroup) =>
      projectGroup.department_id ===
        projectPackagePage.value?.project_group.department_id &&
      projectGroup.project_name_key ===
        projectPackagePage.value?.project_group.project_name_key,
  ),
);

const boolLoading = ref(false);
const boolUpload = ref(false);
const strError = ref("");
let intLoadRevision = 0;

function getPackageLocation(packageId: string): RouteLocationRaw {
  return {
    name: "package-details",
    params: { packageId },
    query: { department_id: arrDepartmentId.value },
  };
}

async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  const strPackageId =
    typeof route.params.packageId === "string" ? route.params.packageId : "";
  boolLoading.value = true;
  strError.value = "";
  details.value = null;
  projectPackagePage.value = null;

  try {
    if (strPackageId) {
      const [projectGroups, projectPackages, packageDetails] = await Promise.all([
        getPackageProjectGroups(arrDepartmentId.value, 1, strPackageId),
        getProjectPackages(strPackageId),
        getPackageDetails(strPackageId),
      ]);
      if (intRevision !== intLoadRevision) return;

      projectGroupPage.value = projectGroups;
      projectPackagePage.value = projectPackages;
      details.value = packageDetails;
    } else {
      const projectGroups = await getPackageProjectGroups(
        arrDepartmentId.value,
        Number(route.query.page) || 1,
      );
      if (intRevision !== intLoadRevision) return;

      projectGroupPage.value = projectGroups;
      const firstProjectGroup = projectGroups.project_groups[0];
      if (firstProjectGroup)
        await router.replace(getPackageLocation(firstProjectGroup.latest_package_id));
    }
  } catch (e) {
    if (intRevision !== intLoadRevision) return;

    projectGroupPage.value = null;
    strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function changeDepartments(ids: string[] | null): void {
  void router.push({ name: "packages", query: { department_id: ids ?? [] } });
}

function changeProjectGroupPage(page: number): void {
  void router.push({
    name: "packages",
    query: { department_id: arrDepartmentId.value, page },
  });
}

async function changeProjectPackagePage(page: number): Promise<void> {
  if (!details.value || boolLoading.value) return;

  const intRevision = ++intLoadRevision;
  const strPackageId = details.value.package.id;
  details.value = null;
  boolLoading.value = true;
  strError.value = "";
  try {
    const projectPackages = await getProjectPackages(strPackageId, page);
    if (intRevision !== intLoadRevision) return;

    const firstPackage = projectPackages.packages[0];
    if (firstPackage) await router.push(getPackageLocation(firstPackage.id));
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function handleUploaded(packageInfo: PackageInfo): void {
  boolUpload.value = false;
  const departmentIds = arrDepartmentId.value;
  void router.push({
    name: "package-details",
    params: { packageId: packageInfo.id },
    query: {
      department_id:
        departmentIds.length && !departmentIds.includes(packageInfo.department_id)
          ? [packageInfo.department_id]
          : departmentIds,
    },
  });
}

function handleDeleted(): void {
  void router.replace({
    name: "packages",
    query: { department_id: arrDepartmentId.value },
  });
}

watch(
  () => route.fullPath,
  () => void load(),
  { immediate: true },
);

onBeforeUnmount(() => {
  intLoadRevision += 1;
});
</script>

<style scoped>
.package-browser {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) minmax(192px, 1fr) minmax(0, 7fr);
  gap: 12px;
  height: calc(100dvh - 176px);
  min-height: 520px;
}

.browser-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.department-label {
  max-width: 100px;
}

@media (max-width: 959px) {
  .package-browser {
    grid-template-columns: minmax(0, 1fr) minmax(192px, 1fr);
    height: auto;
  }

  .browser-column:last-child {
    grid-column: 1 / -1;
  }

  .browser-column:not(:last-child) {
    max-height: 360px;
  }
}
</style>
