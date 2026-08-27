<!-- FileName: DeleteProjectDialog.vue -->
<template>
  <v-dialog v-model="projectStore.showDeleteDialog" width="800px" height="400px">
    <v-card title="Delete Project?">
      <template #text>
        <v-container
          v-if="projectStore.dictDetailEdit"
          fluid
          class="clean-space pa-2 ma-0 fill-height flex-column">
          <v-row class="w-100" style="max-height: 60px">
            <v-col cols="2">
              <v-text-field
                :model-value="projectStore.dictDetailEdit.id"
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

            <v-col cols="8">
              <v-text-field
                :model-value="projectStore.dictDetailEdit.name"
                label="Name"
                class="clean-space"
                density="compact"
                hide-details
                variant="plain"
                readonly>
              </v-text-field>
            </v-col>

            <v-col cols="2">
              <v-text-field
                :model-value="projectStore.dictDetailEdit.version"
                label="Version"
                variant="plain"
                class="clean-space"
                density="compact"
                hide-details
                readonly>
              </v-text-field>
            </v-col>
          </v-row>

          <v-container
            v-if="projectStore.arrBoundSchedule.length !== 0"
            fluid
            class="border-thin flex-column-grow-1 flex-column">
            The following schedules use this project. Modify or delete them before deleting
            the project:
            <v-list
              :items="projectStore.arrBoundSchedule"
              class="clean-space w-100"
              style="width: max-content; flex: 1; min-width: 0px"
              density="compact"
              variant="flat">
            </v-list>
          </v-container>

          <v-container v-else fluid class="border-thin flex-column-grow-1 flex-column">
            No Schedule uses this Project. A Project with a starting, running, or waiting
            Run still cannot be deleted.
          </v-container>
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          prepend-icon="mdi-delete-off-outline"
          @click="projectStore.showDeleteDialog = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          prepend-icon="mdi-delete-empty-outline"
          :disabled="projectStore.arrBoundSchedule.length !== 0"
          @click="projectStore.deleteProject()">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { useProjectStore } from "../../Store/projectStore";

const projectStore = useProjectStore();
</script>

<style scoped></style>
