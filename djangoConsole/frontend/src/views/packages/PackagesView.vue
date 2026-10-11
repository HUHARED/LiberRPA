<!-- FileName: PackagesView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Packages</h1>
    <v-spacer />
    <v-btn v-if="boolCanCreate" color="primary" variant="tonal" @click="boolImport = true">
      Import
    </v-btn>
    <v-btn variant="tonal" :loading="boolLoading" @click="load()">Refresh</v-btn>
  </div>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="arrDepartmentId"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              multiple
              chips
              clearable
              hide-details />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="strProjectName"
              label="Project Name"
              clearable
              hide-details />
          </v-col>
        </v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal">Apply</v-btn>
          <v-btn variant="outlined" @click="clearFilters">Clear Filters</v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
    <p v-if="page">Previously loaded results are shown.</p>
  </v-alert>
  <v-card variant="outlined">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="page?.packages ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :loading="boolLoading"
      disable-sort
      hide-default-footer>
      <template #item.project_name="{ item }">
        <RouterLink :to="{ name: 'package-details', params: { packageId: item.id } }">
          {{ item.project_name }}
        </RouterLink>
      </template>
      <template #item.uploaded_at="{ item }">
        {{ formatDateTime(item.uploaded_at, strTimeZone) }}
      </template>
      <template #item.actions="{ item }">
        <v-btn
          :to="{ name: 'package-details', params: { packageId: item.id } }"
          size="small"
          variant="text">
          View
        </v-btn>
        <v-btn
          v-if="canRun(item.department_id)"
          size="small"
          variant="text"
          @click="strRunPackageId = item.id">
          Run
        </v-btn>
      </template>
      <template #no-data>No packages match the current filters.</template>
    </v-data-table-server>
    <v-divider />
    <div class="d-flex align-center justify-space-between pa-3">
      <span>{{ page?.total_count ?? 0 }} packages</span>
      <v-pagination
        v-if="page && page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="load" />
    </div>
  </v-card>
  <PackageUploadDialog
    v-if="boolImport"
    @close="boolImport = false"
    @saved="handleImported" />
  <RunPackageDialog
    v-if="strRunPackageId"
    :package-id="strRunPackageId"
    @close="strRunPackageId = null"
    @saved="handleRun" />
</template>
<script setup lang="ts">
import { shallowRef, computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PackageUploadDialog from "@/components/packages/PackageUploadDialog.vue";
import RunPackageDialog from "@/components/packages/RunPackageDialog.vue";
import { getPackages, type PackageInfo, type PackagePage } from "@/api/packages";
import { getApiError } from "@/api/errors";
import { useSessionStore } from "@/stores/sessionStore";
import { formatDateTime } from "@/app/formatters";
const ARR_HEADER = [
  { title: "Project Name", key: "project_name" },
  { title: "Version", key: "project_version" },
  { title: "Department", key: "department_path" },
  { title: "Python Environment", key: "python_environment_name" },
  { title: "Uploaded At", key: "uploaded_at" },
  { title: "Uploaded By", key: "uploaded_by_name" },
  { title: "Actions", key: "actions" },
];
const sessionStore = useSessionStore();
const router = useRouter();
const route = useRoute();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolCanCreate = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some((department) => department.role === "developer"),
);
const arrDepartmentId = ref<string[]>(
  typeof route.query.department_id === "string" ? [route.query.department_id] : [],
);
const strProjectName = ref<string | null>("");
let appliedFilters = {
  departmentIds: [...arrDepartmentId.value],
  projectName: strProjectName.value ?? "",
};
const page = shallowRef<PackagePage | null>(null);
const boolImport = ref(false);
const boolLoading = ref(false);
const strError = ref("");
const strRunPackageId = ref<string | null>(null);
function canRun(id: string): boolean {
  return (
    !!sessionStore.access?.is_org_admin ||
    !!sessionStore.access?.departments.some(
      (department) =>
        department.id === id && ["operator", "developer"].includes(department.role ?? ""),
    )
  );
}
let intLoadRevision = 0;
async function load(pageNumber = page.value?.page ?? 1): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getPackages(
      appliedFilters.departmentIds,
      appliedFilters.projectName,
      pageNumber,
    );
    if (intRevision === intLoadRevision) page.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}
function apply(): void {
  appliedFilters = {
    departmentIds: [...arrDepartmentId.value],
    projectName: strProjectName.value ?? "",
  };
  void load(1);
}
function clearFilters(): void {
  arrDepartmentId.value = [];
  strProjectName.value = "";
  apply();
}
function handleImported(packageInfo: PackageInfo): void {
  boolImport.value = false;
  void router.push({ name: "package-details", params: { packageId: packageInfo.id } });
}
function handleRun(): void {
  strRunPackageId.value = null;
  void router.push({ name: "job-queue" });
}
onMounted(() => void load());
</script>
<style scoped></style>
