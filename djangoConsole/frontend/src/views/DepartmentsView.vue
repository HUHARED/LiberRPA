<!-- FileName: DepartmentsView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h6 mb-2">Departments</h2>
      <p class="text-body-2 text-medium-emphasis">
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
        :disabled="boolLoading || boolNewDepartmentOpen || arrDepartmentInfo === null"
        @click="openNewDepartment()">
        New Department
      </v-btn>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading || boolNewDepartmentOpen"
        @click="loadDepartments">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-alert
    v-if="createdDepartment"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    Department "{{ createdDepartment.name }}" created.
  </v-alert>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="arrDepartmentInfo" class="mt-2">
      Previously loaded departments are shown. Refresh to try again.
    </p>
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
          <span class="department-text font-weight-medium" :title="item.path">
            {{ item.name }}
          </span>
        </div>
      </template>
      <template #item.notes="{ item }">
        <div class="department-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>
      <template #item.actions="{ item }">
        <v-btn
          v-if="boolCanManage"
          variant="text"
          size="small"
          prepend-icon="mdi-plus"
          :disabled="boolLoading || boolNewDepartmentOpen"
          :aria-label="`New subdepartment of ${item.path}`"
          @click="openNewDepartment(item.id)">
          New Subdepartment
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
  <v-dialog
    v-model="boolNewDepartmentOpen"
    persistent
    scrollable
    max-width="640"
    aria-labelledby="department-create-title">
    <v-card>
      <v-card-title id="department-create-title">
        {{ strNewParentId === null ? "New Department" : "New Subdepartment" }}
      </v-card-title>
      <v-card-text>
        <v-form
          id="department-create-form"
          validate-on="submit"
          @submit.prevent="submitNewDepartment">
          <v-alert
            v-if="newDepartmentError"
            type="error"
            variant="tonal"
            class="mb-4"
            role="alert">
            Creation was not confirmed. {{ newDepartmentError.message }}
            <p
              v-for="message in newDepartmentError.fields.__all__"
              :key="message"
              class="mt-2">
              {{ message }}
            </p>
          </v-alert>
          <v-text-field
            v-model="strNewName"
            label="Name"
            variant="outlined"
            maxlength="128"
            :rules="[validateNewName]"
            :error-messages="newDepartmentError?.fields.name ?? []"
            :disabled="boolSaving"
            required
            @update:model-value="newDepartmentError = null" />
          <v-select
            v-model="strNewParentId"
            :items="arrParentOption"
            item-title="path"
            item-value="id"
            label="Parent Department"
            variant="outlined"
            :rules="[validateNewParent]"
            :error-messages="newDepartmentError?.fields.parent_id ?? []"
            :disabled="boolSaving"
            @update:model-value="newDepartmentError = null" />
          <v-text-field
            :model-value="strNewPath"
            label="Path"
            variant="outlined"
            readonly />
          <v-textarea
            v-model="strNewNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            counter="2000"
            maxlength="2000"
            :error-messages="newDepartmentError?.fields.notes ?? []"
            :disabled="boolSaving"
            @update:model-value="newDepartmentError = null" />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="boolSaving" @click="closeNewDepartment">
          Cancel
        </v-btn>
        <v-btn
          type="submit"
          form="department-create-form"
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="boolSaving || !boolCanManage">
          Create
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getDepartmentList, createDepartment } from "../api/departments";
import type {
  DepartmentListEntryResponse,
  DepartmentRecordResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

interface DepartmentRow extends DepartmentListEntryResponse {
  depth: number;
}

const ARR_HEADER = [
  { title: "Name", key: "name", minWidth: 240 },
  { title: "Notes", key: "notes", minWidth: 240 },
  { title: "Actions", key: "actions", width: 220 },
];

const sessionStore = useSessionStore();
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const arrDepartmentInfo = shallowRef<DepartmentListEntryResponse[] | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const createdDepartment = shallowRef<DepartmentRecordResponse | null>(null);
const newDepartmentError = shallowRef<ApiError | null>(null);
const strUpdatedAt = ref<string | null>(null);
const boolLoading = ref(false);
const boolNewDepartmentOpen = ref(false);
const boolSaving = ref(false);
const strNewName = ref<string | null>("");
const strNewParentId = ref<string | null>(null);
const strNewNotes = ref<string | null>("");
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
const arrParentOption = computed(() => [
  { id: null, path: "No parent (top level)" },
  ...(arrDepartmentInfo.value ?? []),
]);
const strNewPath = computed(() => {
  if (!strNewName.value) return "";
  const parent = arrDepartmentInfo.value?.find(
    (department) => department.id === strNewParentId.value,
  );
  return parent ? `${parent.path}/${strNewName.value}` : strNewName.value;
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
      boolNewDepartmentOpen.value = false;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function openNewDepartment(parentId: string | null = null): void {
  if (
    !boolCanManage.value ||
    boolLoading.value ||
    boolNewDepartmentOpen.value ||
    arrDepartmentInfo.value === null
  )
    return;
  strNewName.value = "";
  strNewParentId.value = parentId;
  strNewNotes.value = "";
  newDepartmentError.value = null;
  createdDepartment.value = null;
  boolNewDepartmentOpen.value = true;
}

function closeNewDepartment(): void {
  if (!boolSaving.value) boolNewDepartmentOpen.value = false;
}

function validateNewName(value: string | null): true | string {
  if (!value) return "Enter a department name.";
  if (value !== value.trim()) return "The name must not start or end with whitespace.";
  if (value.endsWith(".")) return "The name must not end with a period.";
  if (/[\\/\p{Cc}]/u.test(value))
    return "The name must not contain path separators or control characters.";
  return true;
}

function validateNewParent(value: string | null): true | string {
  return value === null ||
    arrDepartmentInfo.value?.some((department) => department.id === value)
    ? true
    : "Select an available parent department or the top level.";
}

async function submitNewDepartment(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value || !boolNewDepartmentOpen.value) return;
  const validationResult = await event;
  if (
    !validationResult.valid ||
    boolSaving.value ||
    !boolNewDepartmentOpen.value ||
    !boolCanManage.value ||
    boolUnmounted
  )
    return;
  boolSaving.value = true;
  newDepartmentError.value = null;
  try {
    const response = await createDepartment({
      name: strNewName.value ?? "",
      parent_id: strNewParentId.value,
      notes: strNewNotes.value ?? "",
    });
    if (boolUnmounted) return;
    createdDepartment.value = response.department;
    boolNewDepartmentOpen.value = false;
    // Refresh access so the new department is available in other resource forms.
    await Promise.all([loadDepartments(), sessionStore.refreshSession()]);
  } catch (e) {
    if (boolUnmounted) return;
    newDepartmentError.value = getApiError(e);
    if (newDepartmentError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

onMounted(() => void loadDepartments());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped>
.department-text {
  max-width: 360px;
  overflow-wrap: anywhere;
}

.notes-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: pre-line;
}
</style>
