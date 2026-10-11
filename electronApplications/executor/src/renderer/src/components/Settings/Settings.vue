<!-- FileName: Settings.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Settings</v-label>

    <AppearanceSettings />
    <RdpSettings />
    <RetentionSettings />
    <LogAndTimeSettings />
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";
import { debounce } from "lodash";

import AppearanceSettings from "./AppearanceSettings.vue";
import RdpSettings from "./RdpSettings.vue";
import RetentionSettings from "./RetentionSettings.vue";
import LogAndTimeSettings from "./LogAndTimeSettings.vue";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useSettingStore } from "../../Store/settingStore";
import type { ExecutorConfig } from "../../../../shared/config";
import { getErrorMessage } from "../../../../shared/error";

const settingStore = useSettingStore();

const dictConfigExecutor = computed<ExecutorConfig>(() => ({
  theme: settingStore.theme,
  keepRdpSession: settingStore.keepRdpSession,
  keepRdpSessionWidth: settingStore.keepRdpSessionWidth,
  keepRdpSessionHeight: settingStore.keepRdpSessionHeight,
  logRetentionEnabled: settingStore.logRetentionEnabled,
  logRetentionDays: settingStore.logRetentionDays,
  videoRetentionEnabled: settingStore.videoRetentionEnabled,
  videoRetentionDays: settingStore.videoRetentionDays,
  videoStorageLimitEnabled: settingStore.videoStorageLimitEnabled,
  videoStorageLimitGiB: settingStore.videoStorageLimitGiB,
  projectLogFolderPath: settingStore.projectLogFolderPath,
  timezone: settingStore.timezone,
}));

const debouncedSaveConfig = debounce(() => {
  loggerRenderer.info("Modified Executor settings.");
  invokeMain("saveExecutorConfig", dictConfigExecutor.value).catch((e: unknown) => {
    loggerRenderer.error(`Failed to save Executor settings: ${getErrorMessage(e)}`);
  });
}, 300);

watch(dictConfigExecutor, () => {
  debouncedSaveConfig();
});

onBeforeUnmount(() => {
  debouncedSaveConfig.flush();
});
</script>

<style scoped></style>
