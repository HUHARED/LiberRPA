<!-- FileName: ProjectLocalPackage_Dialog_Delete.vue -->
<template>
  <v-dialog v-model="projectStore.showDialog_delete" width="800px" height="400px">
    <v-card title="Delete the project?">
      <template #text>
        <v-container
          v-if="projectStore.dictDetail_edit"
          fluid
          class="clean-space pa-2 ma-0 fill-height flex-column">
          <v-row class="w-100" style="max-height: 60px">
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
                  The task scheduler's ID in database. Managed by Executor.
                </v-tooltip>
              </v-text-field>
            </v-col>

            <v-col cols="8">
              <v-text-field
                v-model="projectStore.dictDetail_edit['name']"
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
                v-model="projectStore.dictDetail_edit['version']"
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
            v-if="projectStore.arrBindScheduler.length !== 0"
            fluid
            class="border-thin flex-column-grow-1 flex-column">
            Some schedulers need it(remember to modify or delete them later):
            <v-list
              :items="projectStore.arrBindScheduler"
              class="clean-space w-100"
              style="width: max-content; flex: 1; min-width: 0px"
              density="compact"
              variant="flat">
            </v-list>
          </v-container>

          <v-container v-else fluid class="border-thin flex-column-grow-1 flex-column">
            Have no scheduler need it.
          </v-container>
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          prepend-icon="mdi-delete-off-outline"
          @click="projectStore.showDialog_delete = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          prepend-icon="mdi-delete-empty-outline"
          @click="projectStore.dbDeleteProject()">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { useProjectStore } from "../store";

const projectStore = useProjectStore();
</script>

<style scoped></style>
