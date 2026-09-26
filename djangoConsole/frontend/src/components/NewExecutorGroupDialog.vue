<!-- FileName: NewExecutorGroupDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="1000"
    aria-labelledby="executor-group-create-title">
    <v-card>
      <v-card-title id="executor-group-create-title">New Group</v-card-title>
      <v-card-text>
        <v-form
          id="executor-group-create-form"
          validate-on="submit"
          @submit.prevent="submitGroup">
          <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
            Creation was not confirmed. {{ saveError.message }}
            <p v-for="message in saveError.fields.__all__" :key="message" class="mt-2">
              {{ message }}
            </p>
          </v-alert>
          <v-alert v-if="!departments.length" type="info" variant="tonal" class="mb-4">
            No departments are available for creation. Ask an organization administrator to
            check departments and your access.
          </v-alert>
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strName"
                label="Name"
                variant="outlined"
                density="compact"
                maxlength="128"
                :rules="[validateName]"
                :error-messages="saveError?.fields.name ?? []"
                :disabled="boolSaving"
                required
                @update:model-value="saveError = null" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="strDepartmentId"
                :items="departments"
                item-title="path"
                item-value="id"
                label="Department"
                variant="outlined"
                density="compact"
                hint="Changing the department clears selected members; the department is fixed after creation."
                persistent-hint
                :rules="[validateDepartment]"
                :error-messages="
                  saveError?.fields.department ?? saveError?.fields.department_id ?? []
                "
                :disabled="boolSaving"
                required />
            </v-col>
          </v-row>
          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            counter="2000"
            maxlength="2000"
            :error-messages="saveError?.fields.notes ?? []"
            :disabled="boolSaving"
            @update:model-value="saveError = null" />
          <h2 class="text-subtitle-1 mb-2">Executors</h2>
          <p class="text-body-2 text-medium-emphasis mb-4">
            Groups may be empty. Unassociated, offline, and paused Executors can be members.
          </p>
          <v-alert v-if="!strDepartmentId" type="info" variant="tonal">
            Select a department to load its Executors.
          </v-alert>
          <template v-else>
            <div class="d-flex flex-wrap align-center ga-2 mb-3">
              <v-text-field
                v-model="strMemberName"
                label="Name"
                aria-label="Filter candidate Executors by name"
                placeholder="Search members by name"
                maxlength="128"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                :disabled="boolSaving || boolLoadingMembers"
                @keydown.enter.prevent="applyMemberFilter" />
              <v-btn
                variant="tonal"
                :disabled="boolSaving || boolLoadingMembers"
                @click="applyMemberFilter">
                Apply
              </v-btn>
              <v-btn
                variant="outlined"
                :disabled="boolSaving || boolLoadingMembers"
                @click="resetMemberFilter">
                Reset
              </v-btn>
              <v-btn
                variant="text"
                :disabled="boolSaving || boolLoadingMembers"
                @click="loadMembers()">
                Refresh
              </v-btn>
            </div>
            <v-alert
              v-if="memberError"
              type="error"
              variant="tonal"
              class="mb-3"
              role="alert">
              {{ memberError.message }}
              <p v-if="memberPage" class="mt-2">
                Previously loaded choices are shown. Refresh to try again.
              </p>
            </v-alert>
            <div class="d-flex flex-wrap align-center justify-space-between ga-2 mb-3">
              <span aria-live="polite">Selected: {{ arrExecutorId.length }}</span>
              <v-btn
                variant="text"
                size="small"
                :disabled="boolSaving || !arrExecutorId.length"
                @click="clearMembers">
                Clear Selection
              </v-btn>
            </div>
            <v-alert
              v-if="saveError?.fields.executor_ids"
              type="error"
              variant="tonal"
              class="mb-3"
              role="alert">
              <p v-for="message in saveError.fields.executor_ids" :key="message">
                {{ message }}
              </p>
            </v-alert>
            <v-data-table-server
              v-model="arrExecutorId"
              :headers="ARR_MEMBER_HEADER"
              :items="memberPage?.executors ?? []"
              :items-length="memberPage?.total_count ?? 0"
              :items-per-page="memberPage?.page_size ?? 50"
              :page="memberPage?.page ?? 1"
              :loading="boolLoadingMembers"
              :mobile-breakpoint="600"
              :item-selectable="() => !boolSaving && !boolLoadingMembers"
              item-value="id"
              select-strategy="page"
              loading-text="Loading Executors…"
              show-select
              disable-sort
              hide-default-footer
              @update:model-value="saveError = null">
              <template #item.name="{ item }">
                <div class="member-text">{{ item.name }}</div>
              </template>
              <template #item.account="{ item }">
                <div class="member-text">
                  {{
                    item.account
                      ? item.account.username
                        ? `${item.account.username} (${item.account.email})`
                        : item.account.email
                      : "—"
                  }}
                </div>
              </template>
              <template #item.association_status="{ item }">
                <span class="text-capitalize">{{ item.association_status }}</span>
              </template>
              <template #item.dispatch_enabled="{ item }">
                {{ item.dispatch_enabled ? "Enabled" : "Paused" }}
              </template>
              <template #no-data>
                {{
                  memberError
                    ? "The Executor choices could not be loaded."
                    : "No Executors match this department and name."
                }}
              </template>
            </v-data-table-server>
            <div
              v-if="memberPage"
              class="d-flex flex-wrap align-center justify-space-between ga-2 mt-3">
              <span class="text-body-2 text-medium-emphasis">
                {{ memberPage.total_count }} Executors · Page {{ memberPage.page }} of
                {{ memberPage.total_pages }}
              </span>
              <v-pagination
                v-if="memberPage.total_pages > 1"
                :model-value="memberPage.page"
                :length="memberPage.total_pages"
                :total-visible="5"
                :disabled="boolSaving || boolLoadingMembers"
                density="comfortable"
                aria-label="Candidate Executor pages"
                @update:model-value="loadMembers" />
            </div>
            <p class="text-body-2 text-medium-emphasis mt-3">
              Select all applies to this page. Selections are kept when filtering or
              changing pages.
            </p>
          </template>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="boolSaving" @click="emit('close')">Cancel</v-btn>
        <v-btn
          type="submit"
          form="executor-group-create-form"
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="boolSaving || boolLoadingMembers || !boolDepartmentAllowed">
          Create
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getExecutorList } from "../api/executors";
import { createExecutorGroup } from "../api/executorGroups";
import type {
  DepartmentAccessResponse,
  ExecutorGroupWriteResponse,
  ExecutorListResponse,
} from "../api/generated/browserApi";

const props = defineProps<{ departments: DepartmentAccessResponse[] }>();
const emit = defineEmits<{ close: []; created: [response: ExecutorGroupWriteResponse] }>();

const ARR_MEMBER_HEADER = [
  { title: "Select", key: "data-table-select", width: 72 },
  { title: "Name", key: "name", minWidth: 180 },
  { title: "Account", key: "account", minWidth: 220 },
  { title: "Association", key: "association_status", minWidth: 140 },
  { title: "Console Dispatch", key: "dispatch_enabled", minWidth: 170 },
];

const sessionStore = useSessionStore();
const strName = ref<string | null>("");
const strNotes = ref<string | null>("");
const strDepartmentId = ref<string | null>(
  props.departments.length === 1 ? props.departments[0]!.id : null,
);
const arrExecutorId = ref<string[]>([]);
const strMemberName = ref<string | null>("");
const memberPage = shallowRef<ExecutorListResponse | null>(null);
const memberError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const boolLoadingMembers = ref(false);
const boolSaving = ref(false);
const boolDepartmentAllowed = computed(
  () => validateDepartment(strDepartmentId.value) === true,
);
let strAppliedMemberName = "";
let intRequestedPage = 1;
let intMemberRevision = 0;
let boolUnmounted = false;

async function loadMembers(pageNumber: number = intRequestedPage): Promise<void> {
  const intCurrentRevision = ++intMemberRevision;
  intRequestedPage = pageNumber;
  memberError.value = null;
  if (!strDepartmentId.value || !boolDepartmentAllowed.value) {
    memberPage.value = null;
    boolLoadingMembers.value = false;
    return;
  }
  boolLoadingMembers.value = true;
  try {
    const response = await getExecutorList(
      {
        name: strAppliedMemberName,
        departmentIds: [strDepartmentId.value],
        dispatchStates: [],
      },
      pageNumber,
    );
    if (intCurrentRevision !== intMemberRevision) return;
    memberPage.value = response;
  } catch (e) {
    if (intCurrentRevision !== intMemberRevision) return;
    memberError.value = getApiError(e);
    if ([401, 403].includes(memberError.value.statusCode)) {
      memberPage.value = null;
      if (memberError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intMemberRevision) boolLoadingMembers.value = false;
  }
}

function applyMemberFilter(): void {
  if (boolSaving.value || boolLoadingMembers.value) return;
  strAppliedMemberName = (strMemberName.value ?? "").trim();
  void loadMembers(1);
}

function resetMemberFilter(): void {
  if (boolSaving.value || boolLoadingMembers.value) return;
  strMemberName.value = "";
  applyMemberFilter();
}

function clearMembers(): void {
  if (boolSaving.value) return;
  arrExecutorId.value = [];
  saveError.value = null;
}

function validateName(value: string | null): true | string {
  return value?.trim() ? true : "Enter a group name.";
}

function validateDepartment(value: string | null): true | string {
  return props.departments.some((department) => department.id === value)
    ? true
    : "Select a department where you can create groups.";
}

async function submitGroup(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value || boolLoadingMembers.value) return;
  const validationResult = await event;
  if (
    !validationResult.valid ||
    boolSaving.value ||
    boolLoadingMembers.value ||
    boolUnmounted ||
    !strDepartmentId.value ||
    !boolDepartmentAllowed.value
  )
    return;
  boolSaving.value = true;
  saveError.value = null;
  try {
    const response = await createExecutorGroup({
      name: (strName.value ?? "").trim(),
      department_id: strDepartmentId.value,
      notes: strNotes.value ?? "",
      executor_ids: [...arrExecutorId.value],
    });
    if (boolUnmounted) return;
    emit("created", response);
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    if ([403, 404].includes(saveError.value.statusCode))
      await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

watch(
  strDepartmentId,
  () => {
    // Selections belong to one department; late responses from a previous selection must not replace its choices.
    arrExecutorId.value = [];
    strMemberName.value = "";
    strAppliedMemberName = "";
    memberPage.value = null;
    saveError.value = null;
    void loadMembers(1);
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  boolUnmounted = true;
  intMemberRevision += 1;
});
</script>

<style scoped>
.member-text {
  max-width: 280px;
  overflow-wrap: anywhere;
}
</style>
