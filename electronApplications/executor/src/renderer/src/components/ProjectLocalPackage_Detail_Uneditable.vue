<!-- FileName: ProjectLocalPackage_Detail_Uneditable.vue -->
<template>
  <v-container v-if="projectStore.dictDetail_edit" fluid class="clean-space">
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="6">
          <v-text-field
            :model-value="
              formatTimestamp(
                projectStore.dictDetail_edit.created_at_ms,
                settingStore.timezone,
              )
            "
            label="Create Time"
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
                projectStore.dictDetail_edit.updated_at_ms,
                settingStore.timezone,
              )
            "
            label="Update Time"
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
        <v-col cols="7">
          <v-text-field
            v-model="projectStore.dictDetail_edit.name"
            label="Name"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>

        <v-col cols="3">
          <v-text-field
            v-model="projectStore.dictDetail_edit.version"
            label="Version"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
          </v-text-field>
        </v-col>

        <v-col cols="2">
          <v-text-field
            v-model="projectStore.dictDetail_edit.id"
            label="ID"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
            <v-tooltip activator="parent" location="top">
              The Project's ID in the Executor database.
            </v-tooltip>
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <v-container fluid class="pa-2 ma-0">
      <v-text-field
        v-model="projectStore.dictDetail_edit.description"
        label="Description"
        class="clean-space"
        density="compact"
        hide-details
        readonly
        variant="plain">
      </v-text-field>

      <v-text-field
        v-model="projectStore.dictDetail_edit.version_summary"
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
import { useProjectStore, useSettingStore } from "../store";
import { formatTimestamp } from "../time";

const projectStore = useProjectStore();
const settingStore = useSettingStore();
</script>

<style scoped></style>
