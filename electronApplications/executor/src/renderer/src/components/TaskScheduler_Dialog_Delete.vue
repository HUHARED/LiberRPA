<!-- FileName: TaskScheduler_Dialog_Delete.vue -->
<template>
  <v-card title="Delete the task scheduler?">
    <template #text>
      <v-container
        v-if="schedulerStore.dictDetail_edit"
        fluid
        class="clean-space pa-2 ma-0 fill-height flex-column">
        <v-row class="w-100">
          <v-col cols="2">
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['id']"
              label="ID"
              class="clean-space"
              density="compact"
              hide-details
              readonly
              variant="plain">
              <v-tooltip activator="parent" location="top">
                The task scheduler's ID in database. Managed by Executor.
              </v-tooltip>
            </v-text-field>
          </v-col>
          <v-col cols="10">
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['name']"
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
          <v-col cols="3">
            <!-- Modify to :items="['local', 'console']" when LiberRPA Console created.-->
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['project_source']"
              label="Source"
              variant="plain"
              class="clean-space"
              density="compact"
              hide-details
              readonly>
            </v-text-field>
          </v-col>

          <v-col cols="2">
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['project_id']"
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

          <v-col cols="5">
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['project_name']"
              label="Name"
              variant="plain"
              class="clean-space"
              density="compact"
              hide-details
              readonly>
            </v-text-field>
          </v-col>

          <!-- Update projectStore.arrVersion by the current project_name -->
          <v-col cols="2">
            <v-text-field
              v-model="schedulerStore.dictDetail_edit['project_version']"
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
        @click="schedulerStore.showDialog_delete = false">
        Cancel
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        prepend-icon="mdi-delete-empty-outline"
        @click="schedulerStore.dbDeleteScheduler()">
        Delete
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { useSchedulerStore } from "../store";

const schedulerStore = useSchedulerStore();
</script>

<style scoped></style>
