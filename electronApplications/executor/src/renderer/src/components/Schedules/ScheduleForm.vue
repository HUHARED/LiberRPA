<!-- FileName: ScheduleForm.vue -->
<template>
  <template v-if="detail">
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="5">
          <v-text-field
            v-model="detail.name"
            label="Name"
            class="clean-space"
            density="compact"
            hide-details
            variant="underlined"></v-text-field>
        </v-col>

        <v-col cols="5">
          <v-select
            v-model="detail.run_conflict_policy"
            label="Conflict Policy"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="ARR_RUN_CONFLICT_POLICY"></v-select>
        </v-col>
      </v-row>

      <v-row class="w-100">
        <v-col cols="5">
          <v-text-field
            v-model="detail.period_start"
            label="Active From"
            type="datetime-local"
            step="1"
            variant="underlined"
            density="compact"
            hide-details
            required
            spellcheck="false">
            <v-tooltip activator="parent" location="top">
              Time zone from Settings: {{ settingStore.timezone }}
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="5">
          <v-text-field
            v-model="detail.period_end"
            label="Active Until"
            type="datetime-local"
            step="1"
            variant="underlined"
            density="compact"
            hide-details
            required
            spellcheck="false">
            <v-tooltip activator="parent" location="top">
              Time zone from Settings: {{ settingStore.timezone }}
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="2" class="pt-0 pb-1">
          <v-container fluid class="clean-space">
            <v-label class="clean-space" style="font-size: 0.75em">Enabled</v-label>

            <v-switch
              v-model="detail.enabled"
              hide-details
              class="clean-space pl-1"
              density="compact"
              true-icon="mdi-flash"></v-switch>
          </v-container>
        </v-col>
      </v-row>

      <v-row class="w-100">
        <v-col cols="3" class="pt-0">
          <v-text-field
            v-model="detail.cron"
            label="Cron Expression"
            class="clean-space"
            density="compact"
            hide-details
            variant="underlined"
            :bg-color="cronValidation.valid ? undefined : 'warning'">
            <v-tooltip activator="parent" location="top">
              {{ cronValidation.valid ? cronValidation.description : cronValidation.error }}
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="9" class="clean-space">
          <v-container fluid class="clean-space pt-0 flex-column">
            <cron-vuetify v-model="detail.cron" class="clean-space mb-2"></cron-vuetify>
          </v-container>
        </v-col>
      </v-row>

      <v-alert
        v-if="cronValidation.valid"
        density="compact"
        variant="plain"
        class="my-2 text-body-2">
        Next:
        {{ arrPreview.join(" · ") || "No upcoming trigger within the active period." }}
      </v-alert>

      <v-divider class="mt-2"></v-divider>

      <v-label class="mt-2 mb-3">Project</v-label>

      <v-row class="w-100">
        <v-col cols="8">
          <v-select
            v-model="detail.project_name"
            label="Name"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="scheduleStore.arrProjectName"
            @update:model-value="whenProjectNameChanged()"></v-select>
        </v-col>

        <v-col cols="4">
          <v-select
            v-model="detail.project_version"
            label="Version"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="detail.project_name ? scheduleStore.arrProjectVersion : []"
            @update:model-value="whenProjectVersionChanged()"></v-select>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
      <v-label>Run Settings</v-label>

      <v-row class="clean-space flex-column-grow-1">
        <v-col cols="5" class="ma-0 px-0 pb-0 pt-3">
          <BuiltInArguments
            v-model:max-retry-count="detail.max_retry_count"
            v-model:timeout-min="detail.timeout_min"
            v-model:log-level="detail.builtin_log_level"
            v-model:record-video="detail.builtin_record_video"
            v-model:stop-shortcut="detail.builtin_stop_shortcut"
            v-model:highlight-ui="detail.builtin_highlight_ui">
            <template #environment>
              <v-text-field
                v-tooltip:top="
                  'The Python environment configured for the selected Package.'
                "
                :model-value="detail.python_environment_name || '—'"
                label="Python Environment"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                readonly />
            </template>
          </BuiltInArguments>
        </v-col>

        <v-col cols="7" class="clean-space flex-column">
          <v-label class="clean-space" style="font-size: 0.75em">
            Custom Project Arguments
          </v-label>

          <CustomArgumentsEditor v-model:custom-args="detail.custom_prj_args" />
        </v-col>
      </v-row>
    </v-container>
  </template>
</template>

<script setup lang="ts">
import { computed } from "vue";

import BuiltInArguments from "../RunSettings/BuiltInArguments.vue";
import CustomArgumentsEditor from "../RunSettings/CustomArgumentsEditor.vue";

import { cloneJsonSerializable } from "../../Common/json";
import {
  formatTimestampForDateTimeLocal,
  parseDateTimeLocalToTimestamp,
} from "../../Common/time";
import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { validateCronExpression } from "../../Schedule/cron";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";
import type { ScheduleFormDraft } from "../../Schedule/types";
import { RunConflictPolicy } from "../../../../shared/runSettings";
import { previewScheduleCron } from "../../../../shared/cron";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

let intProjectSelectionRevision = 0;

const detail = computed<ScheduleFormDraft | undefined>(() => {
  if (scheduleStore.formMode === "new") {
    return scheduleStore.dictDetailNew;
  }
  if (scheduleStore.formMode === "edit") {
    return scheduleStore.dictDetailEdit;
  }
  return undefined;
});

const cronValidation = computed(() => {
  const currentDetail = detail.value;
  return currentDetail === undefined
    ? { valid: false as const, error: "Cron expression is unavailable." }
    : validateCronExpression(currentDetail.cron, settingStore.timezone);
});

const arrPreview = computed(() => {
  const currentDetail = detail.value;
  if (!currentDetail || !cronValidation.value.valid) return [];
  const intStart = parseDateTimeLocalToTimestamp(
    currentDetail.period_start,
    settingStore.timezone,
  );
  const intEnd = parseDateTimeLocalToTimestamp(
    currentDetail.period_end,
    settingStore.timezone,
  );
  if (intStart === undefined || intEnd === undefined) return [];
  return previewScheduleCron(
    currentDetail.cron,
    settingStore.timezone,
    Math.max(Date.now(), intStart - 1),
    intEnd,
  ).map((intTimestamp) =>
    formatTimestampForDateTimeLocal(intTimestamp, settingStore.timezone).replace("T", " "),
  );
});

const ARR_RUN_CONFLICT_POLICY: { title: string; value: RunConflictPolicy }[] = [
  { title: "Skip This Run", value: RunConflictPolicy.Skip },
  { title: "Wait", value: RunConflictPolicy.Wait },
  { title: "Run Concurrently", value: RunConflictPolicy.Concurrent },
];

async function applyProjectDetailToSchedule(
  currentDetail: ScheduleFormDraft,
  name: string,
  version: string,
  intRevision: number,
): Promise<void> {
  const projectDetail = await invokeMain("getProjectDetail", { name, version });
  if (
    intRevision !== intProjectSelectionRevision ||
    detail.value !== currentDetail ||
    currentDetail.project_name !== name ||
    currentDetail.project_version !== version
  ) {
    return;
  }
  if (projectDetail === undefined) {
    throw new Error(`Project not found: ${name}-${version}`);
  }

  currentDetail.project_id = projectDetail.id;
  currentDetail.python_environment_name = projectDetail.python_environment_name;
  currentDetail.max_retry_count = projectDetail.max_retry_count;
  currentDetail.timeout_min = projectDetail.timeout_min;
  currentDetail.builtin_log_level = projectDetail.builtin_log_level;
  currentDetail.builtin_record_video = projectDetail.builtin_record_video;
  currentDetail.builtin_stop_shortcut = projectDetail.builtin_stop_shortcut;
  currentDetail.builtin_highlight_ui = projectDetail.builtin_highlight_ui;
  currentDetail.custom_prj_args = cloneJsonSerializable(projectDetail.custom_prj_args);
}

async function whenProjectNameChanged(): Promise<void> {
  const currentDetail = detail.value;
  if (currentDetail === undefined) {
    return;
  }

  const name = currentDetail.project_name;
  if (name === undefined) {
    return;
  }

  const intRevision = ++intProjectSelectionRevision;
  currentDetail.project_id = undefined;
  currentDetail.project_version = undefined;
  currentDetail.python_environment_name = "";
  scheduleStore.resetProjectVersions();

  loggerRenderer.info(`Modified Project name: ${name}`);
  const arrVersion = await scheduleStore.fetchProjectVersions(name);
  if (
    intRevision !== intProjectSelectionRevision ||
    detail.value !== currentDetail ||
    currentDetail.project_name !== name
  ) {
    return;
  }

  scheduleStore.setProjectVersions(arrVersion);
  const firstVersion = arrVersion[0];
  if (firstVersion === undefined) {
    throw new Error(`No version is available for Project: ${name}`);
  }

  currentDetail.project_version = firstVersion;
  await applyProjectDetailToSchedule(currentDetail, name, firstVersion, intRevision);
}

async function whenProjectVersionChanged(): Promise<void> {
  const currentDetail = detail.value;
  if (currentDetail === undefined) {
    return;
  }

  const name = currentDetail.project_name;
  const version = currentDetail.project_version;
  if (name === undefined || version === undefined) {
    return;
  }

  const intRevision = ++intProjectSelectionRevision;
  currentDetail.project_id = undefined;
  currentDetail.python_environment_name = "";
  loggerRenderer.info(`Modified Project version: ${version}`);
  await applyProjectDetailToSchedule(currentDetail, name, version, intRevision);
}
</script>

<style scoped></style>
