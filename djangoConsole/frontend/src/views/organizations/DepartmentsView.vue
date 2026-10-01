<!-- FileName: DepartmentsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h6 mb-2">Departments</h2>
      <p class="text-medium-emphasis">
        Organize resources and assign access by department. Department access is not
        inherited from a parent department.
      </p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="boolCanManage"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolActionBlocked || arrDepartmentInfo === null"
        @click="openNewDepartment()">
        New Department
      </v-btn>
    </v-col>
  </v-row>
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
    <p v-if="arrDepartmentInfo" class="mt-2">
      Previously loaded departments are shown and may be out of date.
    </p>
    <template #append>
      <v-btn
        variant="tonal"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadDepartments">
        Retry
      </v-btn>
    </template>
  </v-alert>
  <div
    class="d-flex flex-wrap justify-space-between ga-2 mb-3 text-body-2 text-medium-emphasis">
    <span v-if="arrDepartmentInfo" aria-live="polite">
      {{ arrDepartmentInfo.length }} departments
    </span>
    <span v-if="strUpdatedAt">
      Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
    </span>
  </div>
  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table
      :headers="ARR_HEADER"
      :items="arrDepartmentRow"
      :items-per-page="-1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading departments…"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <div
          class="d-flex align-center ga-2"
          :style="{ paddingInlineStart: `${item.depth * 20}px` }">
          <v-icon
            :icon="item.depth ? 'mdi-subdirectory-arrow-right' : 'mdi-folder-outline'"
            size="small"
            aria-hidden="true" />
          <RouterLink
            :to="{ name: 'department-details', params: { departmentId: item.id } }"
            class="table-text text-primary"
            :title="item.path">
            {{ item.name }}
          </RouterLink>
        </div>
      </template>
      <template #item.notes="{ item }">
        <div class="table-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>
      <template #item.actions="{ item }">
        <v-btn
          :to="{ name: 'department-details', params: { departmentId: item.id } }"
          variant="text"
          size="small"
          prepend-icon="mdi-eye-outline"
          :aria-label="`View department ${item.path}`">
          View
        </v-btn>
        <v-btn
          v-if="boolCanManage"
          variant="text"
          size="small"
          prepend-icon="mdi-plus"
          :disabled="boolActionBlocked"
          :aria-label="`New subdepartment of ${item.path}`"
          @click="openNewDepartment(item.id)">
          New Subdepartment
        </v-btn>
        <v-btn
          v-if="boolCanManage"
          variant="text"
          size="small"
          prepend-icon="mdi-pencil-outline"
          :disabled="boolActionBlocked"
          :aria-label="`Edit department ${item.path}`"
          @click="openEditDepartment(item)">
          Edit
        </v-btn>
        <v-btn
          v-if="boolCanManage"
          color="error"
          variant="text"
          size="small"
          prepend-icon="mdi-delete-outline"
          :disabled="boolActionBlocked"
          :aria-label="`Delete department ${item.path}`"
          @click="openDeleteDepartment(item)">
          Delete
        </v-btn>
      </template>
      <template #no-data>
        {{
          requestError
            ? "The department list could not be loaded."
            : "No departments yet. Create a department to organize resources and access."
        }}
      </template>
    </v-data-table>
  </v-card>
  <DepartmentFormDialog
    v-if="boolFormOpen && arrDepartmentInfo"
    :departments="arrDepartmentInfo"
    :department="editTarget ?? undefined"
    :parent-id="strNewParentId"
    @close="closeDepartmentForm"
    @saved="handleDepartmentSaved" />
  <DepartmentDeleteDialog
    v-if="deleteTarget"
    :department="deleteTarget"
    @close="deleteTarget = null"
    @deleted="handleDepartmentDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import DepartmentFormDialog from "@/components/organizations/DepartmentFormDialog.vue";
import DepartmentDeleteDialog from "@/components/organizations/DepartmentDeleteDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getDepartmentList } from "@/api/departments";
import type {
  DeletedDepartmentResponse,
  DepartmentListEntryResponse,
  DepartmentRecordResponse,
} from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

interface DepartmentRow extends DepartmentListEntryResponse {
  depth: number;
}

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 240 },
  { title: "Notes", key: "notes", minWidth: 240 },
  { title: "Actions", key: "actions", width: 480 },
];

const sessionStore = useSessionStore();
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const arrDepartmentInfo = shallowRef<DepartmentListEntryResponse[] | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const editTarget = shallowRef<DepartmentListEntryResponse | null>(null);
const deleteTarget = shallowRef<DepartmentListEntryResponse | null>(null);
const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
const boolLoading = ref(false);
const boolFormOpen = ref(false);
const boolActionBlocked = computed(
  () => boolLoading.value || boolFormOpen.value || deleteTarget.value !== null,
);
const strNewParentId = ref<string | null>(null);
let boolUnmounted = false;

const arrDepartmentRow = computed(() => {
  const mapChildDepartment = new Map<string | null, DepartmentListEntryResponse[]>();
  for (const department of arrDepartmentInfo.value ?? []) {
    const arrChild = mapChildDepartment.get(department.parent_id) ?? [];
    arrChild.push(department);
    mapChildDepartment.set(department.parent_id, arrChild);
  }
  const arrRow: DepartmentRow[] = [];
  function appendChildren(parentId: string | null, depth: number): void {
    for (const department of mapChildDepartment.get(parentId) ?? []) {
      arrRow.push({ ...department, depth });
      appendChildren(department.id, depth + 1);
    }
  }
  // Keep each branch together even when sibling names share a prefix in the path-sorted response.
  appendChildren(null, 0);
  return arrRow;
});

async function loadDepartments(): Promise<void> {
  if (boolLoading.value || !boolCanManage.value) return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getDepartmentList();
    if (boolUnmounted) return;
    arrDepartmentInfo.value = response.departments;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403].includes(requestError.value.statusCode)) {
      arrDepartmentInfo.value = null;
      strUpdatedAt.value = null;
      boolFormOpen.value = false;
      deleteTarget.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function openNewDepartment(parentId: string | null = null): void {
  if (!boolCanManage.value || boolActionBlocked.value || arrDepartmentInfo.value === null)
    return;
  editTarget.value = null;
  strNewParentId.value = parentId;
  strSuccessMessage.value = "";
  boolFormOpen.value = true;
}

function openEditDepartment(department: DepartmentListEntryResponse): void {
  if (!boolCanManage.value || boolActionBlocked.value) return;
  editTarget.value = department;
  strSuccessMessage.value = "";
  boolFormOpen.value = true;
}

function closeDepartmentForm(): void {
  boolFormOpen.value = false;
  editTarget.value = null;
}

function openDeleteDepartment(department: DepartmentListEntryResponse): void {
  if (!boolCanManage.value || boolActionBlocked.value) return;
  deleteTarget.value = department;
  strSuccessMessage.value = "";
}

async function handleDepartmentSaved(department: DepartmentRecordResponse): Promise<void> {
  strSuccessMessage.value = `Department "${department.name}" ${editTarget.value ? "updated" : "created"}.`;
  closeDepartmentForm();
  // Refresh access so resource forms use the current department names and paths.
  await Promise.all([loadDepartments(), sessionStore.refreshSession()]);
}

async function handleDepartmentDeleted(
  department: DeletedDepartmentResponse,
): Promise<void> {
  deleteTarget.value = null;
  strSuccessMessage.value = `Department "${department.name}" deleted.`;
  // Remove the confirmed deletion even if refreshing the remaining tree fails.
  arrDepartmentInfo.value =
    arrDepartmentInfo.value?.filter((entry) => entry.id !== department.id) ?? null;
  strUpdatedAt.value = null;
  await Promise.all([loadDepartments(), sessionStore.refreshSession()]);
}

onMounted(() => void loadDepartments());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
