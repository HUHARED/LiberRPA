<!-- FileName: DepartmentDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="680"
    aria-labelledby="department-delete-title">
    <v-card>
      <v-card-title id="department-delete-title">Delete Department</v-card-title>
      <v-card-text>
        <p class="text-subtitle-1 font-weight-medium department-name mb-4">
          {{ deletionInfo?.department.name ?? department.name }}
        </p>
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{
            requestError.statusCode === 404
              ? "This department does not exist or is no longer available."
              : requestError.message
          }}
        </v-alert>
        <v-alert v-if="deleteError" type="error" variant="tonal" class="mb-4" role="alert">
          Deletion was not confirmed. {{ deleteError.message }}
          <p class="mt-2">Check the current department before trying again.</p>
        </v-alert>
        <v-progress-linear
          v-if="boolLoading"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Checking department deletion conditions" />
        <template v-if="deletionInfo">
          <v-alert
            :type="deletionInfo.can_delete ? 'info' : 'warning'"
            variant="tonal"
            class="mb-4"
            role="status">
            {{
              deletionInfo.can_delete
                ? "No dependencies currently prevent deletion. Conditions will be checked again when you delete."
                : "This department cannot be deleted until the following dependencies are removed."
            }}
          </v-alert>
          <v-table v-if="deletionInfo.blockers.length" class="mb-4">
            <thead>
              <tr>
                <th scope="col">Dependency</th>
                <th scope="col">Count</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="blocker in deletionInfo.blockers" :key="blocker.code">
                <td>{{ dictBlockerDisplay[blocker.code].label }}</td>
                <td>{{ blocker.count }}</td>
                <td>
                  <v-btn
                    :to="dictBlockerDisplay[blocker.code].location"
                    target="_blank"
                    rel="noopener"
                    variant="text"
                    size="small"
                    append-icon="mdi-open-in-new"
                    :disabled="boolBusy || !boolCanManage"
                    :aria-label="`View ${dictBlockerDisplay[blocker.code].label} in a new tab`">
                    View
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
          <p v-if="deletionInfo.blockers.length" class="text-body-2 mb-4">
            View opens a new tab. After removing dependencies, return here and select Check
            Again. Pausing or unassociating an Executor does not remove it.
          </p>
        </template>
        <p class="text-body-2 mb-3">
          Deletion cannot be undone. Your organization and accounts will remain, even if
          this is the last department.
        </p>
        <p class="text-body-2">
          Retained history does not prevent deletion and remains available to organization
          administrators under its retention rules. A new department with the same name will
          not inherit this department's permissions or history.
        </p>
      </v-card-text>
      <v-card-actions class="flex-wrap ga-2">
        <v-spacer />
        <v-btn variant="text" :disabled="boolDeleting" @click="closeDialog">Cancel</v-btn>
        <v-btn
          v-if="requestError || deleteError || (deletionInfo && !deletionInfo.can_delete)"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="boolLoading"
          :disabled="boolBusy || !boolCanManage"
          @click="loadDeletionPreview">
          {{ requestError ? "Retry" : "Check Again" }}
        </v-btn>
        <v-btn
          color="error"
          variant="tonal"
          :loading="boolDeleting"
          :disabled="boolDeleteBlocked"
          @click="submitDelete">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { RouteLocationRaw } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getDepartmentDeletionPreview, deleteDepartment } from "../api/departments";
import type {
  DepartmentDeletionPreviewResponse,
  DepartmentDeletionBlockerResponse,
  DepartmentIdentityResponse,
  DeletedDepartmentResponse,
} from "../api/generated/browserApi";

const props = defineProps<{ department: DepartmentIdentityResponse }>();
const emit = defineEmits<{
  close: [];
  deleted: [department: DeletedDepartmentResponse];
}>();

const dictBlockerDisplay: Record<
  DepartmentDeletionBlockerResponse["code"],
  { label: string; location: RouteLocationRaw }
> = {
  child_departments: { label: "Subdepartments", location: { name: "departments" } },
  department_memberships: {
    label: "Explicit department members",
    location: { name: "department-details", params: { departmentId: props.department.id } },
  },
  executors: {
    label: "Executors",
    location: { name: "executors", query: { department_id: props.department.id } },
  },
  executor_groups: {
    label: "Executor Groups",
    location: { name: "executor-groups", query: { department_id: props.department.id } },
  },
};
const sessionStore = useSessionStore();
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const deletionInfo = shallowRef<DepartmentDeletionPreviewResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const deleteError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolDeleting = ref(false);
const boolBusy = computed(() => boolLoading.value || boolDeleting.value);
const boolDeleteBlocked = computed(
  () => boolBusy.value || !boolCanManage.value || !deletionInfo.value?.can_delete,
);
let boolUnmounted = false;

async function loadDeletionPreview(): Promise<void> {
  if (boolUnmounted || boolBusy.value || !boolCanManage.value) return;
  boolLoading.value = true;
  deletionInfo.value = null;
  requestError.value = null;
  deleteError.value = null;
  try {
    const response = await getDepartmentDeletionPreview(props.department.id);
    if (boolUnmounted) return;
    deletionInfo.value = response;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function closeDialog(): void {
  if (!boolDeleting.value) emit("close");
}

async function submitDelete(): Promise<void> {
  if (boolUnmounted || boolDeleteBlocked.value) return;
  boolDeleting.value = true;
  deleteError.value = null;
  try {
    const response = await deleteDepartment(props.department.id);
    if (boolUnmounted) return;
    if ("blockers" in response) deletionInfo.value = response;
    else emit("deleted", response.department);
  } catch (e) {
    if (boolUnmounted) return;
    deletionInfo.value = null;
    deleteError.value = getApiError(e);
    if (deleteError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolDeleting.value = false;
  }
}

onMounted(() => void loadDeletionPreview());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped>
.department-name {
  overflow-wrap: anywhere;
}
</style>
