<!-- FileName: TaskScheduler_Dialog_Edit.vue -->
<template>
  <v-card v-if="schedulerStore.isEditing === 'edit'" title="Edit the task scheduler">
    <template #text>
      <v-container
        v-if="schedulerStore.dictDetail_edit"
        fluid
        class="clean-space fill-height flex-column">
        <v-container fluid class="pa-2 ma-0">
          <v-row class="w-100">
            <v-col cols="5" class="pb-0">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['created_at']"
                label="Create Time"
                class="clean-space"
                density="compact"
                hide-details
                readonly
                variant="plain">
              </v-text-field>
            </v-col>

            <v-col cols="5" class="pb-0">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['updated_at']"
                label="Update Time"
                class="clean-space"
                density="compact"
                hide-details
                readonly
                variant="plain">
              </v-text-field>
            </v-col>

            <v-col cols="2" class="pb-0">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['id']"
                label="ID"
                class="clean-space"
                density="compact"
                hide-details
                readonly
                variant="plain">
                <v-tooltip activator="parent" location="top">
                  The task scheduler's ID in database. Managed by Executor.
                </v-tooltip>
              </v-text-field>
            </v-col>
          </v-row>

          <v-row class="w-100">
            <v-col cols="5" class="pb-0">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['name']"
                label="Name"
                class="clean-space"
                density="compact"
                hide-details
                variant="underlined">
              </v-text-field>
            </v-col>

            <v-col cols="5" class="pb-0">
              <v-select
                v-model="schedulerStore.dictDetail_edit['when_others_running']"
                label="When other running"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="['cancel', 'wait', 'run']">
              </v-select>
            </v-col>
          </v-row>

          <v-row class="w-100">
            <v-col cols="5">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['period_start']"
                label="Datetime Start"
                type="datetime-local"
                step="1"
                variant="underlined"
                density="compact"
                hide-details
                required
                spellcheck="false">
              </v-text-field>
            </v-col>

            <v-col cols="5">
              <v-text-field
                v-model="schedulerStore.dictDetail_edit['period_end']"
                label="Datetime End"
                type="datetime-local"
                step="1"
                variant="underlined"
                density="compact"
                hide-details
                required
                spellcheck="false">
              </v-text-field>
            </v-col>

            <v-col cols="2" class="pt-0 pb-1">
              <v-container fluid class="clean-space">
                <v-label class="clean-space" style="font-size: 0.75em"> Enable </v-label>

                <v-switch
                  v-model="schedulerStore.dictDetail_edit['enable']"
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
                v-model="schedulerStore.dictDetail_edit['cron']"
                label="Cron"
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
                  v-model="schedulerStore.dictDetail_edit['cron']"
                  class="clean-space mb-2">
                </cron-vuetify>
              </v-container>
            </v-col>
          </v-row>

          <v-divider class="mt-2"></v-divider>

          <v-label class="mt-2 mb-3"> Select Project: </v-label>

          <v-row class="w-100">
            <v-col cols="3">
              <!-- Modify to :items="['local', 'console']" when LiberRPA Console created.-->
              <v-select
                v-model="schedulerStore.dictDetail_edit['project_source']"
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
                v-model="schedulerStore.dictDetail_edit['project_id']"
                label="ID"
                class="clean-space"
                density="compact"
                hide-details
                readonly
                variant="plain">
                <v-tooltip activator="parent" location="top">
                  The project's ID in database. Managed by Executor.
                </v-tooltip>
              </v-text-field>
            </v-col>

            <!-- projectStore.arrName is an array contains "title" attributes, just use it. -->
            <v-col cols="5">
              <v-select
                v-model="schedulerStore.dictDetail_edit['project_name']"
                label="Name"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="projectStore.arrName"
                @update:model-value="whenProjectNameChanged()">
              </v-select>
            </v-col>

            <!-- Update projectStore.arrVersion by the current project_name -->
            <v-col cols="2">
              <v-select
                v-model="schedulerStore.dictDetail_edit['project_version']"
                label="Version"
                variant="underlined"
                class="clean-space"
                density="compact"
                hide-details
                :items="projectStore.arrVersion"
                @update:model-value="whenProjectVersionChanged()">
              </v-select>
            </v-col>
          </v-row>
        </v-container>

        <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
          <v-label> Configure arguments: </v-label>

          <v-row class="clean-space flex-column-grow-1">
            <!-- Left half -->
            <v-col cols="5" class="clean-space fill-height pt-3">
              <!-- Timeout and Log Level -->
              <v-row class="w-100">
                <v-col cols="6">
                  <v-number-input
                    v-model="intTimeoutMin"
                    control-variant="default"
                    label="Timeout"
                    :min="0"
                    :precision="0"
                    inset
                    density="compact"
                    variant="underlined"
                    hide-details>
                    <v-tooltip activator="parent" location="top">
                      If the timeout is reached(in minutes), stop the project. 0 means no
                      limitation.
                    </v-tooltip>
                  </v-number-input>
                </v-col>

                <v-col cols="6">
                  <v-select
                    v-model="schedulerStore.dictDetail_edit['buildin_log_level']"
                    label="Log Level"
                    variant="underlined"
                    class="clean-space"
                    density="compact"
                    hide-details
                    :items="arrLogLevel">
                  </v-select>
                </v-col>
              </v-row>

              <!-- The 3 boolean switches. -->
              <v-container fluid class="clean-space flex-column mt-2">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Record Video
                </v-label>

                <v-switch
                  v-model="schedulerStore.dictDetail_edit['buildin_record_video']"
                  hide-details
                  class="clean-space pl-1"
                  density="compact"
                  true-icon="mdi-video-outline">
                </v-switch>

                <v-label class="clean-space" style="font-size: 0.75em">
                  Stop Shortcut
                </v-label>

                <v-switch
                  v-model="schedulerStore.dictDetail_edit['buildin_stop_shortcut']"
                  hide-details
                  class="clean-space pl-1"
                  density="compact"
                  true-icon="mdi-stop-circle-outline">
                </v-switch>

                <v-label class="clean-space" style="font-size: 0.75em">
                  Highlight UI
                </v-label>

                <v-switch
                  v-model="schedulerStore.dictDetail_edit['buildin_highlight_ui']"
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
                Custom Project Arguments
              </v-label>

              <v-container
                v-if="schedulerStore.dictDetail_edit.custom_prj_args.length !== 0"
                fluid
                class="clean-space flex-column-grow-1 flex-column">
                <v-row
                  v-for="(item, index) in schedulerStore.dictDetail_edit.custom_prj_args"
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
                        updateCusPrjArgsValue(
                          schedulerStore.dictDetail_edit.custom_prj_args,
                          arrValueCache,
                          index,
                          arrValueCache[index]
                        )
                      "
                      @keyup.enter="
                        updateCusPrjArgsValue(
                          schedulerStore.dictDetail_edit.custom_prj_args,
                          arrValueCache,
                          index,
                          arrValueCache[index]
                        )
                      ">
                      <v-tooltip activator="parent" location="top">
                        <span v-html="generateValueNote(item[1])"></span>
                      </v-tooltip>
                    </v-text-field>
                  </v-col>
                </v-row>
              </v-container>

              <v-container v-else fluid class="clean-space">
                No custom project argument.
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
        @click="schedulerStore.showDialog_edit_new = false">
        Cancel
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        prepend-icon="mdi-content-save-outline"
        :disabled="!boolDetailChanged"
        @click="schedulerStore.dbUpdateSchedulerDetail()">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { VNumberInput } from "vuetify/labs/VNumberInput";

import { ref, watch } from "vue";
import { debounce } from "lodash";
import moment from "moment";

import { loggerRenderer } from "../ipcOfRenderer";
import { useSchedulerStore, useProjectStore, useInformationStore } from "../store";
import {
  generateValueNote,
  updateCusPrjArgsValue,
  initCusPrjArgsValueCache,
  updateCusPrjArgsValueCache,
  computedTimeoutMin,
  checkCron,
} from "../commonFunc";
import { arrLogLevel } from "../commonValue";

// console.log("Create TaskScheduler_Dialog_Edit.vue");

const schedulerStore = useSchedulerStore();
const projectStore = useProjectStore();
const informationStore = useInformationStore();

const boolDetailChanged = ref(false);

const intTimeoutMin = computedTimeoutMin(schedulerStore.dictDetail_edit);

const arrValueCache = initCusPrjArgsValueCache(schedulerStore.dictDetail_edit);

const debounced_UpdateValueCahe_SetButtonDisabled = debounce(() => {
  if (!schedulerStore.dictDetail_edit) {
    boolDetailChanged.value = false;
    return;
  }

  // console.log("Update" + JSON.stringify(schedulerStore.dictDetail_edit));

  // Update arrValueCache even the user didn't type a name.
  arrValueCache.value = updateCusPrjArgsValueCache(schedulerStore.dictDetail_edit);

  // Cron must be correct.
  if (!checkCron(schedulerStore.dictDetail_edit.cron)) {
    boolDetailChanged.value = false;
    return;
  }

  // User must type a name, period_start and period_end
  if (
    !schedulerStore.dictDetail_edit.name ||
    !schedulerStore.dictDetail_edit.period_start ||
    !schedulerStore.dictDetail_edit.period_end
  ) {
    boolDetailChanged.value = false;
    return;
  }

  // period_end should later than period_start.
  if (
    moment(schedulerStore.dictDetail_edit.period_end, "YYYY-MM-DD HH:mm:ss").isBefore(
      moment(schedulerStore.dictDetail_edit.period_start, "YYYY-MM-DD HH:mm:ss")
    )
  ) {
    boolDetailChanged.value = false;
    return;
  }

  const strDetailCacheNew = JSON.stringify(schedulerStore.dictDetail_edit);
  if (strDetailCacheNew === schedulerStore.detailCache_edit) {
    /* console.log(
      `Set false\n\n${strDetailCacheNew}\n\n${JSON.stringify(schedulerStore.dictDetail)}`
    ); */
    boolDetailChanged.value = false;
  } else {
    // console.log("Set true");
    boolDetailChanged.value = true;
  }
}, 300);

watch(
  () => schedulerStore.dictDetail_edit,
  () => {
    debounced_UpdateValueCahe_SetButtonDisabled();
  },
  { deep: true }
);

// Update details when project_name modified.
async function whenProjectNameChanged(): Promise<void> {
  if (schedulerStore.dictDetail_edit) {
    const project_name = schedulerStore.dictDetail_edit.project_name;
    loggerRenderer.info("Modified name:" + project_name);

    if (schedulerStore.dictDetail_edit.project_source === "local") {
      // Utilize projectStore's some actions to get data.
      await projectStore.dbSelectProjectVersions(project_name);

      // Use the first version as default.
      schedulerStore.dictDetail_edit.project_version = projectStore.arrVersion[0].title;

      // Update other values
      await updateProjectDetailInScheduler(
        project_name,
        schedulerStore.dictDetail_edit.project_version
      );
    } else {
      // console project.
    }
  }
}

// Update details when project_version modified.
async function whenProjectVersionChanged(): Promise<void> {
  if (schedulerStore.dictDetail_edit) {
    const project_version = schedulerStore.dictDetail_edit.project_version;
    loggerRenderer.info("Modified version:" + project_version);

    if (schedulerStore.dictDetail_edit.project_source === "local") {
      await updateProjectDetailInScheduler(
        schedulerStore.dictDetail_edit.project_name,
        project_version
      );
    } else {
      //  console project.
    }
  }
}

async function updateProjectDetailInScheduler(
  name: string,
  version: string
): Promise<void> {
  // Update projectStore.dictDetail
  await projectStore.dbSelectProjectDetail(name, version);

  // Update other values in projectStore.dictDetail
  if (schedulerStore.dictDetail_edit && projectStore.dictDetail_edit) {
    schedulerStore.dictDetail_edit.project_id = projectStore.dictDetail_edit.id;
    schedulerStore.dictDetail_edit.timeout_min = projectStore.dictDetail_edit.timeout_min;
    schedulerStore.dictDetail_edit.buildin_log_level =
      projectStore.dictDetail_edit.buildin_log_level;
    schedulerStore.dictDetail_edit.buildin_record_video =
      projectStore.dictDetail_edit.buildin_record_video;
    schedulerStore.dictDetail_edit.buildin_stop_shortcut =
      projectStore.dictDetail_edit.buildin_stop_shortcut;
    schedulerStore.dictDetail_edit.buildin_highlight_ui =
      projectStore.dictDetail_edit.buildin_highlight_ui;
    schedulerStore.dictDetail_edit.custom_prj_args =
      projectStore.dictDetail_edit.custom_prj_args;

    loggerRenderer.debug(JSON.stringify(schedulerStore.dictDetail_edit, null, 2));

    // Not update detailCache, otherwise the Save button state is wrong.
  }
}
</script>

<style scoped>
:deep(input) {
  text-overflow: ellipsis;
}
</style>
