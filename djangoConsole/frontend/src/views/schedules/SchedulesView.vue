<!-- FileName: SchedulesView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Schedules</h1>
    <v-spacer />
    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading || boolTargetsLoading"
      :disabled="boolLoading || boolTargetsLoading"
      @click="refresh">
      Refresh
    </v-btn>

    <v-btn
      v-if="boolCanCreate"
      color="primary"
      variant="tonal"
      prepend-icon="mdi-calendar-plus-outline"
      @click="boolNew = true">
      New Schedule
    </v-btn>
  </div>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="4">
            <v-select
              v-model="filters.departmentIds"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              variant="underlined"
              multiple
              chips
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.name"
              label="Name"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.projectName"
              label="Project"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-select
              v-model="filters.enabled"
              :items="ARR_ENABLED"
              label="Enabled"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-autocomplete
              v-model="filters.targetId"
              :items="arrTarget"
              item-title="title"
              item-value="id"
              label="Target"
              variant="underlined"
              clearable
              hide-details
              :loading="boolTargetsLoading" />
          </v-col>
        </v-row>

        <div class="d-flex ga-2 mt-4">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            @click="clearFilters">
            Reset Filters
          </v-btn>
          <v-spacer />
          <v-btn type="submit" color="primary" variant="tonal" prepend-icon="mdi-check">
            Apply
          </v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>

  <v-alert v-if="strTargetError" type="error" variant="tonal" class="mb-4" role="alert">
    Target options could not be loaded. {{ strTargetError }}
  </v-alert>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    The schedule list could not be loaded. {{ requestError.message }}
    <p v-if="page" class="mt-2">
      Previously loaded results are shown. Refresh to try again.
    </p>
  </v-alert>

  <v-alert v-if="strActionError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ strActionError }}
  </v-alert>

  <v-card variant="outlined">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="page?.schedules ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="page?.page_size ?? INT_LIST_PAGE_SIZE"
      :loading="boolLoading"
      disable-sort
      hide-default-footer>
      <template #item.department="{ item }">{{ item.department.path }}</template>

      <template #item.cron="{ item }">
        <p>{{ describeCron(item.cron) }}</p>
        <span class="text-caption">{{ item.time_zone }}</span>
      </template>

      <template #item.run_conflict_policy="{ item }">
        {{ CONFLICT_POLICY_LABELS[item.run_conflict_policy] }}
      </template>

      <template #item.target="{ item }">
        {{
          item.executor_group?.name ||
          item.executors?.map((executor) => executor.name).join(", ") ||
          (item.group_id ? "Executor Group" : `${item.executor_ids.length} Executors`)
        }}
      </template>

      <template #item.enabled="{ item }">
        <v-switch
          :model-value="item.enabled"
          :aria-label="`Enable Schedule ${item.name}`"
          true-icon="mdi-flash"
          hide-details
          density="compact"
          :disabled="!item.can_manage || boolLoading || setChangingId.has(item.id)"
          :loading="setChangingId.has(item.id)"
          @update:model-value="toggle(item, !!$event)" />
      </template>

      <template #item.created_by="{ item }">
        <template v-if="item.created_by">
          <p>{{ item.created_by.username }}</p>
          <span class="text-caption text-medium-emphasis">{{ item.created_by.email }}</span>
        </template>
        <span v-else>—</span>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-if="!item.can_manage"
            v-tooltip:bottom="'View'"
            size="small"
            variant="text"
            aria-label="View"
            icon="mdi-eye-outline"
            :to="{
              name: 'schedule',
              params: { scheduleId: item.id },
              query: route.query,
            }" />

          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Edit'"
            size="small"
            variant="text"
            aria-label="Edit"
            icon="mdi-pencil-outline"
            @click="strEditId = item.id" />

          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Delete'"
            size="small"
            color="error"
            variant="text"
            aria-label="Delete"
            icon="mdi-delete-outline"
            @click="scheduleDelete = item" />
        </div>
      </template>

      <template #no-data>No schedules match the current filters.</template>
    </v-data-table-server>

    <v-divider />

    <div class="d-flex align-center justify-space-between pa-3">
      <span>{{ page?.total_count ?? 0 }} schedules</span>
      <v-pagination
        v-if="page && page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="load" />
    </div>
  </v-card>

  <ScheduleFormDialog
    v-if="boolNew || strEditId || scheduleId"
    :key="strEditId ? `edit:${strEditId}` : (scheduleId ?? 'new')"
    :schedule-id="strEditId ?? scheduleId"
    :readonly="!!scheduleId && !strEditId"
    @edit="strEditId = scheduleId ?? null"
    @close="closeForm"
    @saved="saved" />

  <ScheduleDeleteDialog
    v-if="scheduleDelete"
    :schedule="scheduleDelete"
    @close="scheduleDelete = null"
    @deleted="handleDeleted" />
</template>

<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import cronstrue from "cronstrue";

import { getExecutorList } from "@/api/executors";
import { getExecutorGroupList } from "@/api/executorGroups";

import ScheduleFormDialog from "@/components/schedules/ScheduleFormDialog.vue";
import ScheduleDeleteDialog from "@/components/schedules/ScheduleDeleteDialog.vue";

import {
  type ScheduleListEntry,
  type SchedulePage,
  type ScheduleFilters,
  getSchedules,
  setScheduleEnabled,
} from "@/api/schedules";
import { type ApiError, getApiError } from "@/api/errors";
import { INT_LIST_PAGE_SIZE, DepartmentRole } from "@/api/generated/browserApi";

import { CONFLICT_POLICY_LABELS } from "@/app/runLabels";

import { useSessionStore } from "@/stores/sessionStore";

const ARR_HEADER = [
  { title: "Name", key: "name" },
  { title: "Department", key: "department" },
  { title: "Project Name", key: "project_name" },
  { title: "Project Version", key: "project_version" },
  { title: "Run Time", key: "cron" },
  { title: "Conflict Policy", key: "run_conflict_policy" },
  { title: "Target", key: "target" },
  { title: "Enabled", key: "enabled" },
  { title: "Created By", key: "created_by" },
  { title: "Notes", key: "notes" },
  { title: "Actions", key: "actions" },
];

const ARR_ENABLED = [
  { title: "All", value: "" },
  { title: "Enabled", value: "true" },
  { title: "Disabled", value: "false" },
];

const props = defineProps<{ scheduleId?: string }>();
const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();

const arrRouteDepartmentId = computed(() => {
  const value = route.query.department_id;
  return (Array.isArray(value) ? value : [value]).filter(
    (id): id is string => typeof id === "string" && id !== "",
  );
});

const boolCanCreate = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some(
      (department) => department.role === DepartmentRole.Developer,
    ),
);

function emptyFilters(): ScheduleFilters {
  return { name: "", departmentIds: [], projectName: "", enabled: "", targetId: "" };
}

const arrTarget = ref<{ id: string; title: string }[]>([]);
const boolTargetsLoading = ref(false);
const filters = ref(emptyFilters());
filters.value.departmentIds = [...arrRouteDepartmentId.value];
let appliedFilters = { ...filters.value, departmentIds: [...filters.value.departmentIds] };
const page = shallowRef<SchedulePage | null>(null);
const boolNew = ref(false);
const strEditId = ref<string | null>(null);
const scheduleDelete = shallowRef<ScheduleListEntry | null>(null);
const setChangingId = ref(new Set<string>());
const boolLoading = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const strTargetError = ref("");
const strActionError = ref("");

let intLoadRevision = 0;
let intTargetRevision = 0;
let intRequestedPage = 1;
let boolUnmounted = false;

function describeCron(value: string): string {
  try {
    return cronstrue.toString(value, { use24HourTimeFormat: true });
  } catch {
    return value;
  }
}

async function loadTargets(): Promise<void> {
  const intRevision = ++intTargetRevision;
  boolTargetsLoading.value = true;
  strTargetError.value = "";
  try {
    const arrResult: { id: string; title: string }[] = [];
    const arrPages = await Promise.all([
      getExecutorList({ name: "", departmentIds: [], dispatchStates: [] }, 1),
      getExecutorGroupList({ name: "", departmentIds: [] }, 1),
    ]);
    if (intRevision !== intTargetRevision) return;
    const executorPage = arrPages[0];
    const groupPage = arrPages[1];
    arrResult.push(
      ...executorPage.executors.map((entry) => ({
        id: entry.id,
        title: `Executor: ${entry.name} (${entry.department.path})`,
      })),
    );
    arrResult.push(
      ...groupPage.executor_groups.map((entry) => ({
        id: entry.id,
        title: `Group: ${entry.name} (${entry.department.path})`,
      })),
    );
    for (let intPage = 2; intPage <= executorPage.total_pages; intPage++) {
      const result = await getExecutorList(
        { name: "", departmentIds: [], dispatchStates: [] },
        intPage,
      );
      if (intRevision !== intTargetRevision) return;
      arrResult.push(
        ...result.executors.map((entry) => ({
          id: entry.id,
          title: `Executor: ${entry.name} (${entry.department.path})`,
        })),
      );
    }
    for (let intPage = 2; intPage <= groupPage.total_pages; intPage++) {
      const result = await getExecutorGroupList({ name: "", departmentIds: [] }, intPage);
      if (intRevision !== intTargetRevision) return;
      arrResult.push(
        ...result.executor_groups.map((entry) => ({
          id: entry.id,
          title: `Group: ${entry.name} (${entry.department.path})`,
        })),
      );
    }
    arrTarget.value = arrResult;
  } catch (e) {
    if (intRevision === intTargetRevision) strTargetError.value = getApiError(e).message;
  } finally {
    if (intRevision === intTargetRevision) boolTargetsLoading.value = false;
  }
}

async function load(pageNumber = intRequestedPage): Promise<void> {
  const intRevision = ++intLoadRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getSchedules(appliedFilters, pageNumber);
    if (intRevision === intLoadRevision) page.value = response;
  } catch (e) {
    if (intRevision !== intLoadRevision) return;
    requestError.value = getApiError(e);
    if (requestError.value.code === "invalid_page" && pageNumber > 1) {
      await load(1);
      return;
    }
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

async function refresh(): Promise<void> {
  await Promise.all([load(), loadTargets()]);
}

function apply(): void {
  appliedFilters = { ...filters.value, departmentIds: [...filters.value.departmentIds] };
  void load(1);
}

function clearFilters(): void {
  filters.value = emptyFilters();
  apply();
}

async function toggle(schedule: ScheduleListEntry, enabled: boolean): Promise<void> {
  if (setChangingId.value.has(schedule.id)) return;

  setChangingId.value.add(schedule.id);
  strActionError.value = "";
  try {
    await setScheduleEnabled(schedule.id, enabled);
  } catch (e) {
    if (!boolUnmounted)
      strActionError.value = `Schedule "${schedule.name}" could not be updated. ${getApiError(e).message}`;
    return;
  } finally {
    if (!boolUnmounted) setChangingId.value.delete(schedule.id);
  }

  if (boolUnmounted) return;
  const currentSchedule = page.value?.schedules.find((item) => item.id === schedule.id);
  if (currentSchedule) currentSchedule.enabled = enabled;
  await load();
}

function closeForm(): void {
  boolNew.value = false;
  if (props.scheduleId) void router.replace({ name: "schedules", query: route.query });
  else strEditId.value = null;
}

function saved(): void {
  closeForm();
  void load();
}

function handleDeleted(): void {
  scheduleDelete.value = null;
  void load(1);
}

watch(arrRouteDepartmentId, (departmentIds, previousDepartmentIds) => {
  if (
    departmentIds.length === previousDepartmentIds.length &&
    departmentIds.every((id, index) => id === previousDepartmentIds[index])
  )
    return;

  filters.value.departmentIds = [...departmentIds];
  appliedFilters = { ...appliedFilters, departmentIds: [...departmentIds] };
  page.value = null;
  void load(1);
});

watch(
  () => props.scheduleId,
  () => {
    boolNew.value = false;
    strEditId.value = null;
  },
);

onMounted(() => void refresh());

onBeforeUnmount(() => {
  boolUnmounted = true;
  intLoadRevision += 1;
  intTargetRevision += 1;
});
</script>

<style scoped></style>
