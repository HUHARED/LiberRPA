<!-- FileName: PackagesView.vue -->
<template>
  <v-sheet
    color="transparent"
    class="d-flex flex-column"
    :height="
      mdAndUp
        ? 'calc(100dvh - var(--v-layout-top, 64px) - var(--v-layout-bottom, 0px) - 48px)'
        : undefined
    ">
    <div class="d-flex align-center flex-wrap ga-3 mb-4 flex-shrink-0">
      <h1 class="text-h5">Packages</h1>

      <v-select
        :model-value="arrDepartmentId"
        :items="sessionStore.access?.departments ?? []"
        item-title="path"
        item-value="id"
        label="Department"
        max-width="360"
        class="flex-grow-1"
        variant="underlined"
        density="compact"
        multiple
        chips
        clearable
        hide-details
        @update:model-value="changeDepartments" />
      <v-spacer />

      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        @click="load">
        Refresh
      </v-btn>

      <v-btn
        v-if="boolCanCreate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-upload"
        @click="boolUpload = true">
        Upload Package
      </v-btn>
    </div>

    <v-alert v-if="strError" type="error" variant="tonal" class="mb-4 flex-shrink-0">
      {{ strError }}
    </v-alert>

    <v-row no-gutters class="flex-grow-1 flex-md-nowrap" style="min-height: 0">
      <v-col cols="7" md="3" class="d-flex flex-column border-e-thin">
        <v-card
          variant="flat"
          rounded="0"
          class="d-flex flex-column flex-grow-1"
          style="min-height: 0"
          :height="mdAndUp ? undefined : 360">
          <v-card-title class="text-subtitle-1">Project Name</v-card-title>

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
                  class="ml-2"
                  style="max-width: 100px">
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
      </v-col>

      <v-col
        cols="5"
        md="2"
        class="d-flex flex-column"
        :class="{ 'border-e-thin': mdAndUp }">
        <v-card
          variant="flat"
          rounded="0"
          class="d-flex flex-column flex-grow-1"
          style="min-height: 0"
          :height="mdAndUp ? undefined : 360">
          <v-card-title class="text-subtitle-1 px-2">Project Version</v-card-title>

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
      </v-col>

      <v-col cols="12" md="7" class="d-flex flex-column">
        <v-card
          variant="flat"
          rounded="0"
          class="d-flex flex-column flex-grow-1"
          style="min-height: 0"
          :height="mdAndUp ? undefined : 'max(640px, calc(100dvh - 112px))'">
          <v-card-title class="text-subtitle-1">Package Details</v-card-title>

          <v-divider />
          <v-progress-linear v-if="boolLoading" indeterminate color="primary" />

          <v-card-text class="pa-0 d-flex flex-column" style="min-height: 0">
            <PackageDetailsPanel
              v-if="details"
              :key="details.package.id"
              :details="details"
              @updated="details = $event"
              @deleted="handleDeleted" />

            <p v-else-if="!boolLoading" class="text-medium-emphasis pa-4">
              Select a package to view its details.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-sheet>

  <PackageUploadDialog
    v-if="boolUpload"
    @close="boolUpload = false"
    @saved="handleUploaded" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useDisplay } from "vuetify";
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

const { mdAndUp } = useDisplay();

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

<style scoped></style>
