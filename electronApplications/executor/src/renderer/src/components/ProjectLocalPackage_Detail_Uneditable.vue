<!-- FileName: ProjectLocalPackage_Detail_Uneditable.vue -->
<template>
  <v-container v-if="projectStore.dictDetail_edit" fluid class="clean-space">
    <!-- Create and update datetime -->
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="6">
          <v-text-field
            v-model="projectStore.dictDetail_edit['created_at']"
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
            v-model="projectStore.dictDetail_edit['updated_at']"
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

    <!-- ID, Name and Version -->
    <v-container fluid class="pa-2 ma-0">
      <v-row class="w-100">
        <v-col cols="7">
          <v-text-field
            v-model="projectStore.dictDetail_edit['name']"
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
            v-model="projectStore.dictDetail_edit['version']"
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
            v-model="projectStore.dictDetail_edit['id']"
            label="ID"
            class="clean-space"
            density="compact"
            hide-details
            readonly
            variant="plain">
            <v-tooltip activator="parent" location="top">
              The project's ID in database. Managed by Executor.
            </v-tooltip>
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <!-- Description -->
    <v-container fluid class="pa-2 ma-0">
      <v-text-field
        v-model="projectStore.dictDetail_edit['description']"
        label="Description"
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
import { useProjectStore } from "../store";

const projectStore = useProjectStore();
</script>
<style scoped></style>
