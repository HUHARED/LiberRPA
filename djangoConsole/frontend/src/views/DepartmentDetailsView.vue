<!-- FileName: DepartmentDetailsView.vue -->
<template>
  <v-btn
    :to="{ name: 'departments' }"
    variant="text"
    prepend-icon="mdi-arrow-left"
    class="mb-4">
    Back to Departments
  </v-btn>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h5 mb-2 text-anywhere">
        {{ detailsInfo?.department.name ?? "Department Details" }}
      </h2>
      <p class="text-medium-emphasis">Department Details</p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="detailsInfo && boolCanManage"
        variant="tonal"
        prepend-icon="mdi-pencil-outline"
        :loading="boolOpeningEdit"
        :disabled="boolActionBlocked"
        @click="openEdit">
        Edit
      </v-btn>
      <v-btn
        v-if="detailsInfo && boolCanManage"
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="boolActionBlocked"
        @click="openDelete">
        Delete
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
    {{
      requestError.statusCode === 404
        ? "This department does not exist or is no longer available."
        : requestError.message
    }}
    <p v-if="detailsInfo" class="mt-2">
      Previously loaded details are shown and may be out of date.
    </p>
    <template #append>
      <v-btn
        variant="tonal"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadDepartmentDetails">
        Retry
      </v-btn>
    </template>
  </v-alert>
  <v-progress-linear
    v-if="boolLoading"
    indeterminate
    color="primary"
    class="mb-4"
    aria-label="Loading department details" />
  <template v-if="detailsInfo">
    <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
      Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
    </p>
    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Department Information</v-card-title>
      <v-card-text>
        <dl class="detail-fields">
          <div>
            <dt>Name</dt>
            <dd>{{ detailsInfo.department.name }}</dd>
          </div>
          <div>
            <dt>Parent Department</dt>
            <dd>
              <RouterLink
                v-if="detailsInfo.department.parent_id !== null"
                :to="{
                  name: 'department-details',
                  params: { departmentId: detailsInfo.department.parent_id },
                }"
                class="text-primary">
                {{ strParentPath }}
              </RouterLink>
              <template v-else>No parent (top level)</template>
            </dd>
          </div>
          <div class="full-width-field">
            <dt>Path</dt>
            <dd>{{ detailsInfo.department.path }}</dd>
          </div>
          <div class="full-width-field">
            <dt>Notes</dt>
            <dd class="text-pre-wrap">{{ detailsInfo.department.notes || "—" }}</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Members</v-card-title>
      <v-card-text>
        <p class="mb-3">
          Only explicitly assigned department roles are listed. Organization administrators
          do not need an assignment to access this department.
        </p>
        <v-data-table
          :headers="ARR_MEMBER_HEADER"
          :items="detailsInfo.members"
          :items-per-page="50"
          :items-per-page-options="[50]"
          :hide-default-footer="detailsInfo.members.length <= 50"
          :mobile-breakpoint="600"
          item-value="user.id"
          disable-sort>
          <template #item.account="{ item }">
            <div class="text-anywhere">
              <RouterLink
                :to="{ name: 'member-details', params: { userId: item.user.id } }"
                class="text-primary">
                {{ item.user.username || item.user.email }}
              </RouterLink>
              <p v-if="item.user.username" class="text-body-2 text-medium-emphasis">
                {{ item.user.email }}
              </p>
            </div>
          </template>
          <template #item.role="{ item }">
            <span class="text-capitalize">{{ item.role }}</span>
          </template>
          <template #no-data>No members assigned to this department.</template>
        </v-data-table>
      </v-card-text>
    </v-card>
    <v-card variant="outlined">
      <v-card-title>Resources</v-card-title>
      <v-card-text>
        <p class="mb-3">Open a resource list filtered to this department.</p>
        <div class="d-flex flex-wrap ga-2">
          <v-btn
            :to="{
              name: 'executors',
              query: { department_id: detailsInfo.department.id },
            }"
            variant="tonal"
            prepend-icon="mdi-desktop-classic">
            Executors
          </v-btn>
          <v-btn
            :to="{
              name: 'executor-groups',
              query: { department_id: detailsInfo.department.id },
            }"
            variant="tonal"
            prepend-icon="mdi-group">
            Executor Groups
          </v-btn>
          <v-btn
            :to="{
              name: 'assets',
              query: { department_id: detailsInfo.department.id },
            }"
            variant="tonal"
            prepend-icon="mdi-archive-outline">
            Assets
          </v-btn>
          <v-btn
            :to="{
              name: 'data-queues',
              query: { department_id: detailsInfo.department.id },
            }"
            variant="tonal"
            prepend-icon="mdi-database-outline">
            Data Queues
          </v-btn>
          <v-btn
            :to="{
              name: 'shared-files',
              query: { department_path: '/' + detailsInfo.department.path },
            }"
            variant="tonal"
            prepend-icon="mdi-folder-outline">
            Shared Files
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
  </template>
  <DepartmentFormDialog
    v-if="editTarget"
    :departments="arrEditDepartment"
    :department="editTarget"
    @close="editTarget = null"
    @saved="handleDepartmentSaved" />
  <DepartmentDeleteDialog
    v-if="deleteTarget"
    :department="deleteTarget"
    @close="deleteTarget = null"
    @deleted="handleDepartmentDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";

import DepartmentFormDialog from "../components/DepartmentFormDialog.vue";
import DepartmentDeleteDialog from "../components/DepartmentDeleteDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { ApiError, getApiError } from "../api/errors";
import { getDepartmentList, getDepartmentDetails } from "../api/departments";
import type {
  DeletedDepartmentResponse,
  DepartmentDetailsResponse,
  DepartmentListEntryResponse,
  DepartmentRecordResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const props = defineProps<{ departmentId: string }>();
const ARR_MEMBER_HEADER = [
  { title: "Account", key: "account", minWidth: 240 },
  { title: "Role", key: "role", minWidth: 120 },
];

const sessionStore = useSessionStore();
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const detailsInfo = shallowRef<DepartmentDetailsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const arrEditDepartment = shallowRef<DepartmentListEntryResponse[]>([]);
const editTarget = shallowRef<DepartmentListEntryResponse | null>(null);
const deleteTarget = shallowRef<DepartmentListEntryResponse | null>(null);
const boolLoading = ref(false);
const boolOpeningEdit = ref(false);
const boolDeleted = ref(false);
const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    boolOpeningEdit.value ||
    editTarget.value !== null ||
    deleteTarget.value !== null,
);
const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;

const strParentPath = computed(() => {
  const department = detailsInfo.value?.department;
  if (!department || department.parent_id === null) return "";
  return department.path.slice(0, department.path.lastIndexOf("/"));
});

// TODO: Add remaining resource links when their list pages are available.
async function loadDepartmentDetails(): Promise<void> {
  if (boolDeleted.value) return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getDepartmentDetails(props.departmentId);
    if (intCurrentRevision !== intRequestRevision) return;
    detailsInfo.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    await handleReadError(e);
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

async function handleReadError(error: unknown): Promise<void> {
  requestError.value = getApiError(error);
  if ([401, 403, 404].includes(requestError.value.statusCode)) {
    detailsInfo.value = null;
    editTarget.value = null;
    deleteTarget.value = null;
    strUpdatedAt.value = null;
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  }
}

async function openEdit(): Promise<void> {
  if (!detailsInfo.value || !boolCanManage.value || boolActionBlocked.value) return;
  const intCurrentRevision = intRequestRevision;
  boolOpeningEdit.value = true;
  requestError.value = null;
  strSuccessMessage.value = "";
  try {
    // The details page loads the current tree once to populate the edit form.
    const response = await getDepartmentList();
    if (intCurrentRevision !== intRequestRevision) return;
    const department = response.departments.find(
      (department) => department.id === props.departmentId,
    );
    if (!department) {
      throw new ApiError("Department not found or unavailable.", {
        statusCode: 404,
        code: "department_not_found",
      });
    }
    arrEditDepartment.value = response.departments;
    editTarget.value = department;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    await handleReadError(e);
  } finally {
    if (intCurrentRevision === intRequestRevision) boolOpeningEdit.value = false;
  }
}

async function handleDepartmentSaved(department: DepartmentRecordResponse): Promise<void> {
  editTarget.value = null;
  strSuccessMessage.value = `Department "${department.name}" updated.`;
  // Reload the current path and member snapshot after a confirmed write.
  detailsInfo.value = null;
  strUpdatedAt.value = null;
  await Promise.all([loadDepartmentDetails(), sessionStore.refreshSession()]);
}

function openDelete(): void {
  if (!detailsInfo.value || !boolCanManage.value || boolActionBlocked.value) return;
  deleteTarget.value = detailsInfo.value.department;
  strSuccessMessage.value = "";
}

async function handleDepartmentDeleted(
  department: DeletedDepartmentResponse,
): Promise<void> {
  deleteTarget.value = null;
  detailsInfo.value = null;
  strUpdatedAt.value = null;
  requestError.value = null;
  boolDeleted.value = true;
  strSuccessMessage.value = `Department "${department.name}" deleted.`;
  await sessionStore.refreshSession();
}

watch(
  () => props.departmentId,
  () => {
    detailsInfo.value = null;
    editTarget.value = null;
    deleteTarget.value = null;
    boolOpeningEdit.value = false;
    boolDeleted.value = false;
    strSuccessMessage.value = "";
    strUpdatedAt.value = null;
    void loadDepartmentDetails();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
