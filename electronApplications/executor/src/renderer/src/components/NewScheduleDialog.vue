<template>
  <v-card v-if="scheduleStore.isEditing === 'new'" title="New Schedule">
    <template #text>
      <v-container
        v-if="scheduleStore.dictDetail_new"
        fluid
        class="clean-space fill-height flex-column">
        <v-container fluid class="pa-2 ma-0">
          <v-row class="w-100">
            <v-col cols="5">
              <v-text-field
                v-model="scheduleStore.dictDetail_new['name']"
                label="Name"
                class="clean-space"
                density="compact"
                hide-details
                variant="underlined">
              </v-text-field>
            </v-col>

            <v-col cols="5">
              <v-select
                v-model="scheduleStore.dictDetail_new['when_others_running']"
                label="When Another Run Is Active"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="[
                  { title: 'Skip This Run', value: 'cancel' },
                  { title: 'Wait', value: 'wait' },
                  { title: 'Run Concurrently', value: 'run' },
                ]">
              </v-select>
            </v-col>
          </v-row>

          <v-row class="w-100">
            <v-col cols="5">
              <v-text-field
                v-model="scheduleStore.dictDetail_new['period_start']"
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
                v-model="scheduleStore.dictDetail_new['period_end']"
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
                  v-model="scheduleStore.dictDetail_new['enable']"
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
                v-model="scheduleStore.dictDetail_new['cron']"
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
                <cron-vuetify
                  v-model="scheduleStore.dictDetail_new['cron']"
                  class="clean-space mb-2">
                </cron-vuetify>
              </v-container>
            </v-col>
          </v-row>

          <v-divider class="mt-2"></v-divider>

          <v-label class="mt-2 mb-3"> Project </v-label>

          <v-row class="w-100">
            <v-col cols="3">
              <!-- Modify to :items="['local', 'console']" when LiberRPA Console created.-->
              <v-select
                v-model="scheduleStore.dictDetail_new['project_source']"
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
                v-model="scheduleStore.dictDetail_new['project_id']"
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

            <!-- projectStore.arrName is an array contains "title" attributes, just use it. -->
            <v-col cols="5">
              <v-select
                v-model="scheduleStore.dictDetail_new['project_name']"
                label="Name"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="projectStore.arrName"
                @update:model-value="whenProjectNameChanged()">
              </v-select>
            </v-col>

            <!-- Update projectStore.arrVersion by the current project_name, if the project_name is not specified, use [] -->
            <v-col cols="2">
              <v-select
                v-model="scheduleStore.dictDetail_new['project_version']"
                label="Version"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="
                  scheduleStore.dictDetail_new['project_name']
                    ? projectStore.arrVersion
                    : []
                "
                @update:model-value="whenProjectVersionChanged()">
              </v-select>
            </v-col>
          </v-row>
        </v-container>

        <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
          <v-label> Run Options </v-label>

          <v-row class="clean-space flex-column-grow-1">
            <!-- Left half -->
            <v-col cols="5" class="clean-space fill-height pt-3">
              <!-- Timeout and Log Level -->
              <v-row class="w-100">
                <v-col cols="6">
                  <v-number-input
                    v-model="intTimeoutMin"
                    control-variant="default"
                    label="Timeout (min)"
                    :min="0"
                    :precision="0"
                    inset
                    density="compact"
                    variant="underlined"
                    hide-details>
                    <v-tooltip activator="parent" location="top">
                      Stop the run when it exceeds this timeout. 0 means no limit.
                    </v-tooltip>
                  </v-number-input>
                </v-col>

                <v-col cols="6">
                  <v-select
                    v-model="scheduleStore.dictDetail_new['builtin_log_level']"
                    label="Log Level"
                    variant="underlined"
                    class="clean-space"
                    density="compact"
                    hide-details
                    :items="ARR_LOG_LEVEL">
                  </v-select>
                </v-col>
              </v-row>

              <!-- The 3 boolean switches. -->
              <v-container fluid class="clean-space flex-column mt-2">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Record Video
                </v-label>

                <v-switch
                  v-model="scheduleStore.dictDetail_new['builtin_record_video']"
                  hide-details
                  class="clean-space pl-1"
                  density="compact"
                  true-icon="mdi-video-outline">
                </v-switch>

                <v-label class="clean-space" style="font-size: 0.75em">
                  Stop Shortcut
                </v-label>

                <v-switch
                  v-model="scheduleStore.dictDetail_new['builtin_stop_shortcut']"
                  hide-details
                  class="clean-space pl-1"
                  density="compact"
                  true-icon="mdi-stop-circle-outline">
                </v-switch>

                <v-label class="clean-space" style="font-size: 0.75em">
                  Highlight UI
                </v-label>

                <v-switch
                  v-model="scheduleStore.dictDetail_new['builtin_highlight_ui']"
                  hide-details
                  class="clean-space pl-1"
                  density="compact"
                  true-icon="mdi-rectangle-outline">
                </v-switch>
              </v-container>
            </v-col>

            <!-- Right half: Custom Project Arguments -->
            <v-col cols="7" class="clean-space flex-column">
              <v-label class="clean-space" style="font-size: 0.75em">
                Custom Arguments
              </v-label>

              <v-container
                v-if="scheduleStore.dictDetail_new.custom_prj_args.length !== 0"
                fluid
                class="clean-space flex-column-grow-1 flex-column">
                <v-row
                  v-for="(item, index) in scheduleStore.dictDetail_new.custom_prj_args"
                  :key="index"
                  class="clean-space"
                  style="width: 100%; max-height: 40px">
                  <v-col cols="6" class="pa-0 ma-0">
                    <v-text-field
                      v-model="item[0]"
                      variant="plain"
                      density="comfortable"
                      hide-details
                      readonly
                      spellcheck="false">
                      <v-tooltip activator="parent" location="top">
                        {{ item[0] }}
                      </v-tooltip>
                    </v-text-field>
                  </v-col>

                  <!-- The equal symbol. -->
                  <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

                  <!-- The variable's value, it must can be deserialized. -->
                  <v-col cols="5" class="pa-0 ma-0">
                    <v-text-field
                      v-if="arrValueCache"
                      v-model="arrValueCache[index]"
                      variant="underlined"
                      density="comfortable"
                      hide-details
                      spellcheck="false"
                      @blur="
                        updateCustomProjectArgumentValue(
                          scheduleStore.dictDetail_new.custom_prj_args,
                          arrValueCache,
                          index,
                          arrValueCache[index],
                        )
                      "
                      @keyup.enter="
                        updateCustomProjectArgumentValue(
                          scheduleStore.dictDetail_new.custom_prj_args,
                          arrValueCache,
                          index,
                          arrValueCache[index],
                        )
                      ">
                      <v-tooltip activator="parent" location="top">
                        <span v-html="getArgumentValueNote(item[1])"></span>
                      </v-tooltip>
                    </v-text-field>
                  </v-col>
                </v-row>
              </v-container>

              <v-container v-else fluid class="clean-space">
                No custom arguments.
              </v-container>
            </v-col>
          </v-row>
        </v-container>
      </v-container>
    </template>

    <v-divider></v-divider>

    <v-card-actions class="bg-surface-light">
      <v-btn
        prepend-icon="mdi-content-save-off-outline"
        @click="scheduleStore.showDialog_edit_new = false">
        Cancel
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        prepend-icon="mdi-content-save-outline"
        :disabled="!boolDetailChanged"
        @click="scheduleStore.createSchedule()">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { debounce } from "lodash";

import { loggerRenderer } from "../Logging/logger";
import { validateCron } from "../Schedule/cron";
import { useInformationStore } from "../Store/informationStore";
import { useProjectStore } from "../Store/projectStore";
import { useScheduleStore } from "../Store/scheduleStore";
import { useSettingStore } from "../Store/settingStore";
import {
  ARR_LOG_LEVEL,
  getArgumentValueNote,
  updateCustomProjectArgumentValue,
  createCustomProjectArgumentValueCache,
  getCustomProjectArgumentValueCache,
  createTimeoutMinModel,
} from "../RunOptions/runOptions";
import { parseDateTimeLocalToTimestamp } from "../Common/time";

const scheduleStore = useScheduleStore();
const projectStore = useProjectStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

const boolDetailChanged = ref(false);

const intTimeoutMin = createTimeoutMinModel(scheduleStore.dictDetail_new);

const arrValueCache = createCustomProjectArgumentValueCache(scheduleStore.dictDetail_new);

const debouncedUpdateValueCacheAndButtonState = debounce(() => {
  // Update arrValueCache even the user didn't type a name.
  if (scheduleStore.dictDetail_new) {
    arrValueCache.value = getCustomProjectArgumentValueCache(scheduleStore.dictDetail_new);
  }

  // Cron must be correct.
  if (scheduleStore.dictDetail_new && !validateCron(scheduleStore.dictDetail_new.cron)) {
    boolDetailChanged.value = false;
    return;
  }

  if (
    scheduleStore.dictDetail_new === undefined ||
    scheduleStore.dictDetail_new.name === "" ||
    scheduleStore.dictDetail_new.project_id === undefined ||
    scheduleStore.dictDetail_new.period_start === "" ||
    scheduleStore.dictDetail_new.period_end === ""
  ) {
    boolDetailChanged.value = false;
    return;
  }

  const intPeriodStartMs = parseDateTimeLocalToTimestamp(
    scheduleStore.dictDetail_new.period_start,
    settingStore.timezone,
  );
  const intPeriodEndMs = parseDateTimeLocalToTimestamp(
    scheduleStore.dictDetail_new.period_end,
    settingStore.timezone,
  );
  if (
    intPeriodStartMs === undefined ||
    intPeriodEndMs === undefined ||
    intPeriodEndMs <= intPeriodStartMs
  ) {
    boolDetailChanged.value = false;
    return;
  }

  boolDetailChanged.value = true;
}, 300);

watch(
  () => scheduleStore.dictDetail_new,
  () => {
    debouncedUpdateValueCacheAndButtonState();
  },
  { deep: true },
);

// Update details when project_name is modified.
async function whenProjectNameChanged(): Promise<void> {
  const dictDetail = scheduleStore.dictDetail_new;
  if (
    dictDetail === undefined ||
    dictDetail.project_source !== "local" ||
    dictDetail.project_name === undefined
  ) {
    return;
  }

  const strProjectName = dictDetail.project_name;
  loggerRenderer.info(`Modified Project name: ${strProjectName}`);
  await projectStore.loadProjectVersions(strProjectName);

  const firstVersion = projectStore.arrVersion[0];
  if (firstVersion === undefined) {
    throw new Error(`No version is available for Project: ${strProjectName}`);
  }

  dictDetail.project_version = firstVersion.title;
  await applyProjectDetailToSchedule(strProjectName, firstVersion.title);
}

// Update details when project_version is modified.
async function whenProjectVersionChanged(): Promise<void> {
  const dictDetail = scheduleStore.dictDetail_new;
  if (
    dictDetail === undefined ||
    dictDetail.project_source !== "local" ||
    dictDetail.project_name === undefined ||
    dictDetail.project_version === undefined
  ) {
    return;
  }

  loggerRenderer.info(`Modified Project version: ${dictDetail.project_version}`);
  await applyProjectDetailToSchedule(dictDetail.project_name, dictDetail.project_version);
}

async function applyProjectDetailToSchedule(name: string, version: string): Promise<void> {
  // Update projectStore.dictDetail
  await projectStore.loadProjectDetail(name, version);

  // Update other values in projectStore.dictDetail
  if (scheduleStore.dictDetail_new && projectStore.dictDetail_edit) {
    scheduleStore.dictDetail_new.project_id = projectStore.dictDetail_edit.id;
    scheduleStore.dictDetail_new.timeout_min = projectStore.dictDetail_edit.timeout_min;
    scheduleStore.dictDetail_new.builtin_log_level =
      projectStore.dictDetail_edit.builtin_log_level;
    scheduleStore.dictDetail_new.builtin_record_video =
      projectStore.dictDetail_edit.builtin_record_video;
    scheduleStore.dictDetail_new.builtin_stop_shortcut =
      projectStore.dictDetail_edit.builtin_stop_shortcut;
    scheduleStore.dictDetail_new.builtin_highlight_ui =
      projectStore.dictDetail_edit.builtin_highlight_ui;
    scheduleStore.dictDetail_new.custom_prj_args =
      projectStore.dictDetail_edit.custom_prj_args;

    loggerRenderer.debug(JSON.stringify(scheduleStore.dictDetail_new, null, 2));
  }
}
</script>

<style scoped>
:deep(input) {
  text-overflow: ellipsis;
}
</style>
