<!-- FileName: ProjectLocalPackage_Detail_BuildinArgs.vue -->
<template>
  <v-col v-if="projectStore.dictDetail_edit" cols="6" class="clean-space fill-height pt-3">
    <!-- Timeout and Log Level -->
    <v-row class="w-100">
      <v-col cols="7">
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
            If the timeout is reached(in minutes), stop the project. 0 means no limitation.
          </v-tooltip>
        </v-number-input>
      </v-col>

      <v-col cols="5">
        <v-select
          v-model="projectStore.dictDetail_edit['buildin_log_level']"
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
      <v-label class="clean-space" style="font-size: 0.75em"> Record Video </v-label>

      <v-switch
        v-model="projectStore.dictDetail_edit['buildin_record_video']"
        hide-details
        class="clean-space pl-1"
        density="compact"
        true-icon="mdi-video-outline">
      </v-switch>

      <v-label class="clean-space" style="font-size: 0.75em"> Stop Shortcut </v-label>

      <v-switch
        v-model="projectStore.dictDetail_edit['buildin_stop_shortcut']"
        hide-details
        class="clean-space pl-1"
        density="compact"
        true-icon="mdi-stop-circle-outline">
      </v-switch>

      <v-label class="clean-space" style="font-size: 0.75em"> Highlight UI </v-label>

      <v-switch
        v-model="projectStore.dictDetail_edit['buildin_highlight_ui']"
        hide-details
        class="clean-space pl-1"
        density="compact"
        true-icon="mdi-rectangle-outline">
      </v-switch>
    </v-container>
  </v-col>
</template>

<script setup lang="ts">
import { VNumberInput } from "vuetify/labs/VNumberInput";
import { useProjectStore } from "../store";
import { computedTimeoutMin } from "../commonFunc";
import { arrLogLevel } from "../commonValue";

const projectStore = useProjectStore();

const intTimeoutMin = computedTimeoutMin(projectStore.dictDetail_edit);
</script>

<style scoped></style>
