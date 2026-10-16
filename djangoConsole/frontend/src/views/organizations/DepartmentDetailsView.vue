<!-- FileName: DepartmentDetailsView.vue -->
<template>
  <v-btn
    :to="{ name: 'departments' }"
    variant="tonal"
    prepend-icon="mdi-arrow-left"
    class="mb-4">
    Back to Departments
  </v-btn>

  <h2 class="text-h5 mb-2 text-anywhere">
    {{ detailsInfo?.department.name ?? "Department Details" }}
  </h2>

  <p class="text-medium-emphasis mb-6">Department Details</p>

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
        prepend-icon="mdi-refresh"
        size="small"
        :disabled="boolLoading"
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
            <dt class="text-caption text-medium-emphasis">Name</dt>
            <dd>{{ detailsInfo.department.name }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Parent Department</dt>

            <dd>
              <RouterLink
                v-if="detailsInfo.department.parent_id !== null"
                :to="{
                  name: 'department-details',
                  params: { departmentId: detailsInfo.department.parent_id },
                }"
                class="text-primary text-decoration-none">
                {{ strParentPath }}
              </RouterLink>
              <template v-else>No parent (top level)</template>
            </dd>
          </div>

          <div class="full-width-field">
            <dt class="text-caption text-medium-emphasis">Path</dt>
            <dd>{{ detailsInfo.department.path }}</dd>
          </div>

          <div class="full-width-field">
            <dt class="text-caption text-medium-emphasis">Notes</dt>
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
                class="text-primary text-decoration-none">
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
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getDepartmentDetails } from "@/api/departments";
import type { DepartmentDetailsResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

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

async function handleReadError(error: unknown): Promise<void> {
  requestError.value = getApiError(error);
  if ([401, 403, 404].includes(requestError.value.statusCode)) {
    detailsInfo.value = null;
    strUpdatedAt.value = null;
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  }
}

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
    await handleReadError(e);
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

<style scoped></style>
