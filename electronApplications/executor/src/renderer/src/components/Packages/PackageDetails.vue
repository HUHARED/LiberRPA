<!-- FileName: PackageDetails.vue -->
<template>
  <v-container v-if="packageStore.dictDetailEdit" fluid class="clean-space">
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="6">
          <v-text-field
            :model-value="
              formatTimestamp(
                packageStore.dictDetailEdit.created_at_ms,
                settingStore.timezone,
              )
            "
            label="Installed At"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain"></v-text-field>
        </v-col>

        <v-col cols="6">
          <v-text-field
            :model-value="
              formatTimestamp(
                packageStore.dictDetailEdit.updated_at_ms,
                settingStore.timezone,
              )
            "
            label="Updated At"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain"></v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="6">
          <v-text-field
            :model-value="packageStore.dictDetailEdit.project_name"
            label="Project Name"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain"></v-text-field>
        </v-col>

        <v-col cols="6">
          <v-text-field
            :model-value="packageStore.dictDetailEdit.project_version"
            label="Project Version"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain"></v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0">
      <v-text-field
        :model-value="packageStore.dictDetailEdit.description"
        label="Description"
        class="clean-space mb-2"
        density="compact"
        hide-details
        readonly
        variant="plain"></v-text-field>

      <v-text-field
        :model-value="packageStore.dictDetailEdit.version_summary"
        label="Version Summary"
        class="clean-space"
        density="compact"
        hide-details
        readonly
        variant="plain"></v-text-field>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { usePackageStore } from "../../Store/packageStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";

const packageStore = usePackageStore();
const settingStore = useSettingStore();
</script>

<style scoped></style>
