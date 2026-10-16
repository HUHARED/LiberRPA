<!-- FileName: SchedulesView.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Schedules</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-calendar-plus-outline"
        @click="newSchedule()">
        New Schedule
      </v-btn>
    </v-container>

    <v-divider class="w-100" />

    <v-alert v-if="strError" type="error" variant="tonal" class="my-2">
      {{ strError }}
    </v-alert>

    <v-data-table
      :headers="arrHeader"
      :items="scheduleStore.arrListItem"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
      <template #item.cron="{ value }">
        <v-chip
          :text="
            cronstrue.toString(value, {
              use24HourTimeFormat: true,
              throwExceptionOnParseError: false,
              verbose: true,
            })
          "
          variant="tonal"
          size="small"></v-chip>
      </template>

      <template #item.enabled="{ item }">
        <v-switch
          :model-value="item.enabled"
          :aria-label="`Enable Schedule ${item.name}`"
          true-icon="mdi-flash"
          density="compact"
          hide-details
          :loading="setChangingId.has(item.id)"
          :disabled="setChangingId.has(item.id)"
          @update:model-value="toggleSchedule(item, $event === true)" />
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-tooltip text="Edit Schedule" location="bottom" :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-pencil-outline"
                size="small"
                @click="editSchedule(item.name)"></v-icon>
            </template>
          </v-tooltip>

          <v-tooltip text="Delete Schedule" location="bottom" :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-delete-outline"
                size="small"
                @click="openDeleteDialog(item.name)"></v-icon>
            </template>
          </v-tooltip>
        </div>
      </template>
    </v-data-table>

    <ScheduleFormDialog v-if="scheduleStore.showFormDialog" />

    <ScheduleDeleteDialog v-if="scheduleStore.showDeleteDialog" />
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount, ref } from "vue";
import type { DataTableHeader } from "vuetify";
import cronstrue from "cronstrue";

import ScheduleDeleteDialog from "./ScheduleDeleteDialog.vue";
import ScheduleFormDialog from "./ScheduleFormDialog.vue";

import { invokeMain } from "../../IPC/ipc";
import { getDefaultSchedulePeriod } from "../../Common/time";
import { loggerRenderer } from "../../Logging/logger";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";
import { getErrorMessage } from "../../../../shared/error";
import { LogLevel, RunConflictPolicy } from "../../../../shared/runSettings";
import type { ScheduleListItem } from "../../../../shared/schedule";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();
const setChangingId = ref(new Set<number>());
const strError = ref("");

onBeforeMount(() => {
  void Promise.all([
    scheduleStore.loadScheduleList(),
    scheduleStore.loadProjectNames(),
  ]).catch((e: unknown) => {
    loggerRenderer.error(`Failed to initialize Schedules: ${getErrorMessage(e)}`);
  });
});

function newSchedule(): void {
  loggerRenderer.debug("--newSchedule--");

  scheduleStore.invalidateScheduleDetailSelection();
  scheduleStore.resetProjectVersions();
  const dictDefaultPeriod = getDefaultSchedulePeriod(settingStore.timezone);
  scheduleStore.dictDetailNew = {
    name: "",
    project_id: undefined,
    project_name: undefined,
    project_version: undefined,
    python_environment_name: "",
    cron: "0 8 * * *",
    run_conflict_policy: RunConflictPolicy.Skip,
    period_start: dictDefaultPeriod.periodStartLocal,
    period_end: dictDefaultPeriod.periodEndLocal,
    enabled: true,
    max_retry_count: 0,
    timeout_min: 0,
    builtin_log_level: LogLevel.Debug,
    builtin_record_video: true,
    builtin_stop_shortcut: true,
    builtin_highlight_ui: false,
    custom_prj_args: [],
  };

  scheduleStore.formMode = "new";
  scheduleStore.showFormDialog = true;
}

const arrHeader: DataTableHeader<ScheduleListItem>[] = [
  { title: "Name", value: "name", align: "start", sortable: true },
  {
    title: "Project",
    align: "center",
    children: [
      { title: "Name", value: "project_name", align: "start", sortable: true },
      {
        title: "Version",
        value: "project_version",
        align: "start",
        sortable: true,
      },
    ],
  },
  { title: "Schedule", value: "cron", align: "start", sortable: true },
  { title: "Enabled", value: "enabled", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

async function toggleSchedule(item: ScheduleListItem, enabled: boolean): Promise<void> {
  if (setChangingId.value.has(item.id)) return;

  const boolOriginalEnabled = item.enabled;
  item.enabled = enabled;
  setChangingId.value.add(item.id);
  strError.value = "";
  try {
    await invokeMain("setScheduleEnabled", { id: item.id, enabled });
  } catch (e: unknown) {
    item.enabled = boolOriginalEnabled;
    strError.value = getErrorMessage(e);
    loggerRenderer.error(`Failed to update Schedule ${item.id}: ${strError.value}`);
  } finally {
    setChangingId.value.delete(item.id);
  }
}

async function editSchedule(scheduleName: string): Promise<void> {
  loggerRenderer.info(`Edit schedule: ${scheduleName}`);
  const detail = await scheduleStore.loadScheduleDetail(scheduleName);
  if (detail === undefined) {
    return;
  }

  const intRevision = scheduleStore.intDetailLoadRevision;

  await scheduleStore.loadProjectNames();
  if (intRevision !== scheduleStore.intDetailLoadRevision) {
    return;
  }

  const arrVersion = await scheduleStore.fetchProjectVersions(detail.project_name);
  if (intRevision !== scheduleStore.intDetailLoadRevision) {
    return;
  }

  scheduleStore.setProjectVersions(arrVersion);
  scheduleStore.formMode = "edit";
  scheduleStore.showFormDialog = true;
}

async function openDeleteDialog(scheduleName: string): Promise<void> {
  loggerRenderer.info(`Open delete dialog for schedule: ${scheduleName}`);

  const detail = await scheduleStore.loadScheduleDetail(scheduleName);
  if (detail === undefined) {
    return;
  }

  scheduleStore.showDeleteDialog = true;
}
</script>

<style scoped></style>
