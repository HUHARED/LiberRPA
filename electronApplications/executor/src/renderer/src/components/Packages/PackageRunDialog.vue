<!-- FileName: PackageRunDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolStarting"
    max-width="1000"
    height="100%"
    scrollable
    @update:model-value="!$event && emit('close')">
    <v-card title="Run">
      <v-card-text class="flex-column overflow-hidden">
        <p class="text-subtitle-1 mb-3 flex-shrink-0 text-break">
          {{ packageDetails.project_name }} · {{ packageDetails.project_version }}
        </p>

        <h2 class="text-h6 mb-3 flex-shrink-0">Run Settings</h2>

        <v-row class="flex-column-grow-1 overflow-hidden">
          <v-col cols="12" md="6">
            <h3 class="text-subtitle-1 mb-3">Built-in Arguments</h3>

            <BuiltInArguments
              v-model:max-retry-count="runSettings.max_retry_count"
              v-model:timeout-min="runSettings.timeout_min"
              v-model:log-level="runSettings.builtin_log_level"
              v-model:record-video="runSettings.builtin_record_video"
              v-model:stop-shortcut="runSettings.builtin_stop_shortcut"
              v-model:highlight-ui="runSettings.builtin_highlight_ui">
              <template #environment>
                <v-select
                  v-model="runSettings.python_environment_name"
                  v-tooltip:top="
                    'The Python environment used to run this Package. Loaded from envs\\pyenv.'
                  "
                  label="Python Environment"
                  variant="underlined"
                  density="compact"
                  :loading="boolLoading"
                  :items="arrPythonEnvironmentName" />
              </template>
            </BuiltInArguments>
          </v-col>

          <v-col cols="12" md="6" class="flex-column">
            <h3 class="text-subtitle-1 mb-3 flex-shrink-0">Custom Project Arguments</h3>
            <CustomArgumentsEditor v-model:custom-args="runSettings.custom_prj_args" />
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolStarting"
          @click="emit('close')">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-play-outline"
          color="primary"
          :loading="boolStarting"
          :disabled="boolLoading"
          @click="submitRun">
          Run
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import BuiltInArguments from "../RunSettings/BuiltInArguments.vue";
import CustomArgumentsEditor from "../RunSettings/CustomArgumentsEditor.vue";

import { cloneJsonSerializable } from "../../Common/json";
import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useRunHistoryStore } from "../../Store/runHistoryStore";
import { getErrorMessage } from "../../../../shared/error";
import type { PackageDetails, PackageSettingsUpdate } from "../../../../shared/package";

const props = defineProps<{ packageDetails: PackageDetails }>();
const emit = defineEmits<{ close: [] }>();
const runHistoryStore = useRunHistoryStore();
const runSettings = ref<PackageSettingsUpdate>(cloneJsonSerializable(props.packageDetails));
const arrPythonEnvironmentName = ref<string[]>([]);
const boolLoading = ref(true);
const boolStarting = ref(false);

async function submitRun(): Promise<void> {
  if (boolLoading.value || boolStarting.value) return;
  boolStarting.value = true;
  try {
    const settings = runSettings.value;
    await invokeMain("runPackage", {
      id: settings.id,
      python_environment_name: settings.python_environment_name,
      max_retry_count: settings.max_retry_count,
      timeout_min: settings.timeout_min,
      builtin_log_level: settings.builtin_log_level,
      builtin_record_video: settings.builtin_record_video,
      builtin_stop_shortcut: settings.builtin_stop_shortcut,
      builtin_highlight_ui: settings.builtin_highlight_ui,
      custom_prj_args: cloneJsonSerializable(settings.custom_prj_args),
    });
    emit("close");
    await runHistoryStore.refreshRunHistory();
  } catch (e: unknown) {
    loggerRenderer.error(
      `Failed to run Package ${props.packageDetails.id}: ${getErrorMessage(e)}`,
    );
  } finally {
    boolStarting.value = false;
  }
}

onMounted(async () => {
  try {
    arrPythonEnvironmentName.value = await invokeMain("getPythonEnvironmentNames");
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to load Python environments: ${getErrorMessage(e)}`);
  } finally {
    boolLoading.value = false;
  }
});
</script>

<style scoped></style>
