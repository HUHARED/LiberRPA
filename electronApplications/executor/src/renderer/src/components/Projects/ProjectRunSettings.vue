<!-- FileName: ProjectRunSettings.vue -->
<template>
  <v-col v-if="projectStore.dictDetailEdit" cols="6" class="clean-space fill-height pt-3">
    <v-select
      v-model="projectStore.dictDetailEdit.python_environment_name"
      label="Python Environment"
      variant="underlined"
      class="clean-space mb-2"
      density="compact"
      hide-details
      :items="projectStore.arrPythonEnvironmentName">
      <v-tooltip activator="parent" location="top">
        The LiberRPA Python environment used to run this Project. Environments are loaded
        from envs\pyenv.
      </v-tooltip>
    </v-select>

    <BuiltInRunOptions
      v-model:timeout-min="projectStore.dictDetailEdit.timeout_min"
      v-model:log-level="projectStore.dictDetailEdit.builtin_log_level"
      v-model:record-video="projectStore.dictDetailEdit.builtin_record_video"
      v-model:stop-shortcut="projectStore.dictDetailEdit.builtin_stop_shortcut"
      v-model:highlight-ui="projectStore.dictDetailEdit.builtin_highlight_ui"
      :timeout-cols="7"
      :log-level-cols="5" />
  </v-col>
</template>

<script setup lang="ts">
import BuiltInRunOptions from "../RunOptions/BuiltInRunOptions.vue";
import { useProjectStore } from "../../Store/projectStore";

const projectStore = useProjectStore();
</script>

<style scoped></style>
