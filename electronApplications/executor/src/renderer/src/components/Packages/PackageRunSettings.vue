<!-- FileName: PackageRunSettings.vue -->
<template>
  <v-col v-if="packageStore.dictDetailEdit" cols="6" class="clean-space fill-height pt-3">
    <v-alert
      v-if="
        !packageStore.arrPythonEnvironmentName.includes(
          packageStore.dictDetailEdit.python_environment_name,
        )
      "
      type="warning"
      variant="tonal"
      density="compact">
      This Python environment is currently unavailable. You can save its name and install
      the environment before running.
    </v-alert>

    <BuiltInArguments
      v-model:max-retry-count="packageStore.dictDetailEdit.max_retry_count"
      v-model:timeout-min="packageStore.dictDetailEdit.timeout_min"
      v-model:log-level="packageStore.dictDetailEdit.builtin_log_level"
      v-model:record-video="packageStore.dictDetailEdit.builtin_record_video"
      v-model:stop-shortcut="packageStore.dictDetailEdit.builtin_stop_shortcut"
      v-model:highlight-ui="packageStore.dictDetailEdit.builtin_highlight_ui">
      <template #environment>
        <v-select
          v-model="packageStore.dictDetailEdit.python_environment_name"
          v-tooltip:top="
            'The Python environment used to run this Package. Loaded from envs\\pyenv.'
          "
          label="Python Environment"
          variant="underlined"
          class="clean-space mb-2"
          density="compact"
          hide-details
          :items="packageStore.arrPythonEnvironmentName" />
      </template>
    </BuiltInArguments>
  </v-col>
</template>

<script setup lang="ts">
import BuiltInArguments from "../RunSettings/BuiltInArguments.vue";

import { usePackageStore } from "../../Store/packageStore";

const packageStore = usePackageStore();
</script>

<style scoped></style>
