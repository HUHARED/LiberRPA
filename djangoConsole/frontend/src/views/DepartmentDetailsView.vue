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
      <h2 class="text-h5 mb-2 department-text">
        {{ detailsInfo?.department.name ?? "Department Details" }}
      </h2>
      <p class="text-body-2 text-medium-emphasis">Department Details</p>
    </v-col>
    <v-col cols="auto">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="loadDepartmentDetails">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{
      requestError.statusCode === 404
        ? "This department does not exist or is no longer available."
        : requestError.message
    }}
    <p v-if="detailsInfo" class="mt-2">
      Previously loaded details are shown. Refresh to try again.
    </p>
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
        <dl class="department-fields">
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
            <dd class="department-notes">{{ detailsInfo.department.notes || "—" }}</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Members</v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">
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
            <div class="department-text">
              <span>{{ item.user.username || item.user.email }}</span>
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
        <p class="text-body-2 text-medium-emphasis mb-3">
          Open a resource list filtered to this department.
        </p>
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
        </div>
      </v-card-text>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getDepartmentDetails } from "../api/departments";
import type { DepartmentDetailsResponse } from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

const props = defineProps<{ departmentId: string }>();
const ARR_MEMBER_HEADER = [
  { title: "Account", key: "account", minWidth: 240 },
  { title: "Role", key: "role", minWidth: 120 },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const detailsInfo = shallowRef<DepartmentDetailsResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;

const strParentPath = computed(() => {
  const department = detailsInfo.value?.department;
  if (!department || department.parent_id === null) return "";
  return department.path.slice(0, department.path.lastIndexOf("/"));
});

// TODO: Add department editing and deletion through the existing administration APIs.
// TODO: Add remaining resource links when their list pages are available.
async function loadDepartmentDetails(): Promise<void> {
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
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      detailsInfo.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

watch(
  () => props.departmentId,
  () => {
    detailsInfo.value = null;
    strUpdatedAt.value = null;
    void loadDepartmentDetails();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped>
.department-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 20px;
}

.department-fields dt {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  margin-bottom: 4px;
}

.department-fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.full-width-field {
  grid-column: 1 / -1;
}

.department-text {
  overflow-wrap: anywhere;
}

.department-notes {
  white-space: pre-wrap;
}
</style>
