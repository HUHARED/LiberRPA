<!-- FileName: SocketState.vue -->

<template>
  <div style="position: absolute; top: 35px; right: 10px">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          v-if="settingStore.socketState"
          v-bind="props"
          icon="mdi-link-variant"
          color="primary">
        </v-icon>
        <v-icon v-else v-bind="props" icon="mdi-link-variant-remove" color="error">
        </v-icon>
      </template>
      <span>{{
        settingStore.socketState
          ? "LiberRPA Local Server is connected."
          : "LiberRPA Local Server is not connected."
      }}</span>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
import { useSettingStore } from "../store";

const settingStore = useSettingStore();
</script>

<style scoped></style>
