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
            variant="underlined">
          </v-text-field>
        </v-col>

        <v-col cols="5">
          <v-select
            v-model="detail.when_others_running"
            label="When Another Run Is Active"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="ARR_WHEN_OTHERS_RUNNING">
          </v-select>
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
              Interpreted using Executor time zone: {{ settingStore.timezone }}
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
              Interpreted using Executor time zone: {{ settingStore.timezone }}
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="2" class="pt-0 pb-1">
          <v-container fluid class="clean-space">
            <v-label class="clean-space" style="font-size: 0.75em"> Enabled </v-label>

            <v-switch
              v-model="detail.enable"
              hide-details
              class="clean-space pl-1"
              density="compact"
              true-icon="mdi-flash">
            </v-switch>
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
            :bg-color="informationStore.showAlert ? 'warning' : undefined">
            <v-tooltip activator="parent" location="top">
              {{ informationStore.information }}
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="9" class="clean-space">
          <v-container fluid class="clean-space pt-0 flex-column">
            <cron-vuetify v-model="detail.cron" class="clean-space mb-2"> </cron-vuetify>
          </v-container>
        </v-col>
      </v-row>

      <v-divider class="mt-2"></v-divider>

      <v-label class="mt-2 mb-3"> Project </v-label>

      <v-row class="w-100">
        <v-col cols="3">
          <!-- Modify to :items="['local', 'console']" when LiberRPA Console is created. -->
          <v-select
            v-model="detail.project_source"
            label="Source"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="['local']">
          </v-select>
        </v-col>

        <v-col cols="2">
          <v-text-field
            v-model="detail.project_id"
            label="ID"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
            <v-tooltip activator="parent" location="top">
              Internal project ID managed by Executor.
            </v-tooltip>
          </v-text-field>
        </v-col>

        <v-col cols="5">
          <v-select
            v-model="detail.project_name"
            label="Name"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="projectStore.arrName"
            @update:model-value="whenProjectNameChanged()">
          </v-select>
        </v-col>

        <v-col cols="2">
          <v-select
            v-model="detail.project_version"
            label="Version"
            variant="underlined"
            class="clean-space"
            density="compact"
            hide-details
            :items="detail.project_name ? projectStore.arrVersion : []"
            @update:model-value="whenProjectVersionChanged()">
          </v-select>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
      <v-label> Run Options </v-label>

      <v-row class="clean-space flex-column-grow-1">
        <v-col cols="5" class="clean-space fill-height pt-3">
          <BuiltInRunOptions
            v-model:timeout-min="detail.timeout_min"
            v-model:log-level="detail.builtin_log_level"
            v-model:record-video="detail.builtin_record_video"
            v-model:stop-shortcut="detail.builtin_stop_shortcut"
            v-model:highlight-ui="detail.builtin_highlight_ui" />
        </v-col>

        <v-col cols="7" class="clean-space flex-column">
          <v-label class="clean-space" style="font-size: 0.75em">
            Custom Arguments
          </v-label>

          <CustomArgumentsEditor v-model:custom-args="detail.custom_prj_args" />
        </v-col>
      </v-row>
    </v-container>
  </template>
</template>

<script setup lang="ts">
import { computed } from "vue";

import BuiltInRunOptions from "../RunOptions/BuiltInRunOptions.vue";
import CustomArgumentsEditor from "../RunOptions/CustomArgumentsEditor.vue";

import { cloneJsonSerializable } from "../../Common/json";
import { loggerRenderer } from "../../Logging/logger";
import { useInformationStore } from "../../Store/informationStore";
import { useProjectStore } from "../../Store/projectStore";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";
import type { TypeScheduleFormDetail } from "../../Schedule/types";
import type { TypeWhenOthersRunning } from "../../../../shared/schedule";

const projectStore = useProjectStore();
const scheduleStore = useScheduleStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

const detail = computed<TypeScheduleFormDetail | undefined>(() => {
  if (scheduleStore.formMode === "new") {
    return scheduleStore.dictDetail_new;
  }
  if (scheduleStore.formMode === "edit") {
    return scheduleStore.dictDetail_edit;
  }
  return undefined;
});

const ARR_WHEN_OTHERS_RUNNING: { title: string; value: TypeWhenOthersRunning }[] = [
  { title: "Skip This Run", value: "cancel" },
  { title: "Wait", value: "wait" },
  { title: "Run Concurrently", value: "run" },
];

async function whenProjectNameChanged(): Promise<void> {
  const currentDetail = detail.value;
  if (currentDetail === undefined) {
    return;
  }

  const name = currentDetail.project_name;
  if (currentDetail.project_source !== "local" || name === undefined) {
    return;
  }

  loggerRenderer.info(`Modified Project name: ${name}`);
  await projectStore.loadProjectVersions(name);

  const firstVersion = projectStore.arrVersion[0];
  if (firstVersion === undefined) {
    throw new Error(`No version is available for Project: ${name}`);
  }

  currentDetail.project_version = firstVersion.title;
  await applyProjectDetailToSchedule(currentDetail, name, firstVersion.title);
}

async function whenProjectVersionChanged(): Promise<void> {
  const currentDetail = detail.value;
  if (currentDetail === undefined) {
    return;
  }

  const name = currentDetail.project_name;
  const version = currentDetail.project_version;
  if (
    currentDetail.project_source !== "local" ||
    name === undefined ||
    version === undefined
  ) {
    return;
  }

  loggerRenderer.info(`Modified Project version: ${version}`);
  await applyProjectDetailToSchedule(currentDetail, name, version);
}

async function applyProjectDetailToSchedule(
  currentDetail: TypeScheduleFormDetail,
  name: string,
  version: string,
): Promise<void> {
  await projectStore.loadProjectDetail(name, version);

  const projectDetail = projectStore.dictDetail_edit;
  if (projectDetail === undefined) {
    return;
  }

  currentDetail.project_id = projectDetail.id;
  currentDetail.timeout_min = projectDetail.timeout_min;
  currentDetail.builtin_log_level = projectDetail.builtin_log_level;
  currentDetail.builtin_record_video = projectDetail.builtin_record_video;
  currentDetail.builtin_stop_shortcut = projectDetail.builtin_stop_shortcut;
  currentDetail.builtin_highlight_ui = projectDetail.builtin_highlight_ui;
  currentDetail.custom_prj_args = cloneJsonSerializable(projectDetail.custom_prj_args);
}
</script>

<style scoped></style>
