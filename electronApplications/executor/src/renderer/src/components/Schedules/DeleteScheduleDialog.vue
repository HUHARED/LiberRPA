<template>
  <v-card title="Delete Schedule?">
    <template #text>
      <v-container
        v-if="scheduleStore.dictDetailEdit"
        fluid
        class="clean-space pa-2 ma-0 fill-height flex-column">
        <v-row class="w-100">
          <v-col cols="2">
            <v-text-field
              :model-value="scheduleStore.dictDetailEdit.id"
              label="ID"
              class="clean-space"
              density="compact"
              hide-details
              readonly
              variant="plain">
              <v-tooltip activator="parent" location="top">
                Internal schedule ID managed by Executor.
              </v-tooltip>
            </v-text-field>
          </v-col>
          <v-col cols="10">
            <v-text-field
              :model-value="scheduleStore.dictDetailEdit.name"
              label="Name"
              class="clean-space"
              density="compact"
              hide-details
              variant="plain"
              readonly>
            </v-text-field>
          </v-col>
        </v-row>

        <v-container class="clean-space pl-3">
          <v-label class="mt-2 mb-3"> Project: </v-label>
        </v-container>

        <v-row class="w-100">
          <v-col cols="2">
            <v-text-field
              :model-value="scheduleStore.dictDetailEdit.project_id"
              label="ID"
              class="clean-space"
              density="compact"
              hide-details
              readonly
              variant="plain">
              <v-tooltip activator="parent" location="top">
                Internal project ID managed by Executor.
              </v-tooltip>
            </v-text-field>
          </v-col>

          <v-col cols="7">
            <v-text-field
              :model-value="scheduleStore.dictDetailEdit.project_name"
              label="Name"
              variant="plain"
              class="clean-space"
              density="compact"
              hide-details
              readonly>
            </v-text-field>
          </v-col>

          <v-col cols="3">
            <v-text-field
              :model-value="scheduleStore.dictDetailEdit.project_version"
              label="Version"
              variant="plain"
              class="clean-space"
              density="compact"
              hide-details
              readonly>
            </v-text-field>
          </v-col>
        </v-row>
      </v-container>
    </template>

    <v-divider></v-divider>

    <v-card-actions class="bg-surface-light">
      <v-btn
        prepend-icon="mdi-delete-off-outline"
        @click="scheduleStore.showDeleteDialog = false">
        Cancel
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        prepend-icon="mdi-delete-empty-outline"
        @click="scheduleStore.deleteSchedule()">
        Delete
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { useScheduleStore } from "../../Store/scheduleStore";

const scheduleStore = useScheduleStore();
</script>

<style scoped></style>
