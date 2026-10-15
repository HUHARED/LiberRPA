<!-- FileName: ProjectRunSettings.vue -->
<template>
  <v-col v-if="projectStore.dictDetailEdit" cols="6" class="clean-space fill-height pt-3">
    <v-alert
      v-if="
        !projectStore.arrPythonEnvironmentName.includes(
          projectStore.dictDetailEdit.python_environment_name,
        )
      "
      type="warning"
      variant="tonal"
      density="compact">
      This Python environment is currently unavailable. You can save its name and install
      the environment before running.
    </v-alert>

    <BuiltInArguments
      v-model:max-retry-count="projectStore.dictDetailEdit.max_retry_count"
      v-model:timeout-min="projectStore.dictDetailEdit.timeout_min"
      v-model:log-level="projectStore.dictDetailEdit.builtin_log_level"
      v-model:record-video="projectStore.dictDetailEdit.builtin_record_video"
      v-model:stop-shortcut="projectStore.dictDetailEdit.builtin_stop_shortcut"
      v-model:highlight-ui="projectStore.dictDetailEdit.builtin_highlight_ui">
      <template #environment>
        <v-select
          v-model="projectStore.dictDetailEdit.python_environment_name"
          v-tooltip:top="
            'The Python environment used to run this Project. Loaded from envs\\pyenv.'
          "
          label="Python Environment"
          variant="underlined"
          class="clean-space mb-2"
          density="compact"
          hide-details
          :items="projectStore.arrPythonEnvironmentName" />
      </template>
    </BuiltInArguments>
  </v-col>
</template>

<script setup lang="ts">
import BuiltInArguments from "../RunSettings/BuiltInArguments.vue";

import { useProjectStore } from "../../Store/projectStore";

const projectStore = useProjectStore();
</script>

<style scoped></style>
