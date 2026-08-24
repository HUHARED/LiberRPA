<template>
  <v-col v-if="projectStore.dictDetail_edit" cols="6" class="clean-space fill-height pt-3">
    <v-select
      v-model="projectStore.dictDetail_edit.python_environment_name"
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
      v-model:timeout-min="projectStore.dictDetail_edit.timeout_min"
      v-model:log-level="projectStore.dictDetail_edit.builtin_log_level"
      v-model:record-video="projectStore.dictDetail_edit.builtin_record_video"
      v-model:stop-shortcut="projectStore.dictDetail_edit.builtin_stop_shortcut"
      v-model:highlight-ui="projectStore.dictDetail_edit.builtin_highlight_ui"
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
