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
import LogAndTimeSettings from "./LogAndTimeSettings.vue";
import RdpSettings from "./RdpSettings.vue";
import RetentionSettings from "./RetentionSettings.vue";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useSettingStore } from "../../Store/settingStore";
import type { DictExecutorConfig } from "../../../../shared/config";

const settingStore = useSettingStore();

const dictConfigExecutor = computed<DictExecutorConfig>(() => ({
  theme: settingStore.theme,
  keepRdpSession: settingStore.keepRdpSession,
  keepRdpSessionWidth: settingStore.keepRdpSessionWidth,
  keepRdpSessionHeight: settingStore.keepRdpSessionHeight,
  logTimeoutEnable: settingStore.logTimeoutEnable,
  logTimeoutDays: settingStore.logTimeoutDays,
  videoTimeoutEnable: settingStore.videoTimeoutEnable,
  videoTimeoutDays: settingStore.videoTimeoutDays,
  videoSizeEnable: settingStore.videoSizeEnable,
  videoSizeGB: settingStore.videoSizeGB,
  projectLogFolderPath: settingStore.projectLogFolderPath,
  timezone: settingStore.timezone,
}));

const debouncedSaveConfig = debounce(() => {
  loggerRenderer.info("Modified Executor settings.");
  invokeMain("saveExecutorConfig", dictConfigExecutor.value).catch((e: unknown) => {
    loggerRenderer.error(`Failed to save Executor settings: ${String(e)}`);
  });
}, 300);

watch(dictConfigExecutor, () => {
  debouncedSaveConfig();
});

onBeforeUnmount(() => {
  debouncedSaveConfig.cancel();
});
</script>

<style scoped></style>
