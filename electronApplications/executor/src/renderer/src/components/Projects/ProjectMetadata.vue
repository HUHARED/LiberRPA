<!-- FileName: ProjectMetadata.vue -->
<template>
  <v-container v-if="projectStore.dictDetailEdit" fluid class="clean-space">
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="6">
          <v-text-field
            :model-value="
              formatTimestamp(
                projectStore.dictDetailEdit.created_at_ms,
                settingStore.timezone,
              )
            "
            label="Installed At"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>

        <v-col cols="6">
          <v-text-field
            :model-value="
              formatTimestamp(
                projectStore.dictDetailEdit.updated_at_ms,
                settingStore.timezone,
              )
            "
            label="Updated At"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="8">
          <v-text-field
            :model-value="projectStore.dictDetailEdit.name"
            label="Name"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>

        <v-col cols="4">
          <v-text-field
            :model-value="projectStore.dictDetailEdit.version"
            label="Version"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0">
      <v-text-field
        :model-value="projectStore.dictDetailEdit.description"
        label="Description"
        class="clean-space mb-2"
        density="compact"
        hide-details
        readonly
        variant="plain">
      </v-text-field>

      <v-text-field
        :model-value="projectStore.dictDetailEdit.version_summary"
        label="Version Summary"
        class="clean-space"
        density="compact"
        hide-details
        readonly
        variant="plain">
      </v-text-field>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { useProjectStore } from "../../Store/projectStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";

const projectStore = useProjectStore();
const settingStore = useSettingStore();
</script>

<style scoped></style>
