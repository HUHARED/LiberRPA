<!-- FileName: ScheduleDeleteDialog.vue -->
<template>
  <v-dialog
    v-model="scheduleStore.showDeleteDialog"
    width="400px"
    :persistent="boolDeleting">
    <v-card title="Delete Schedule">
      <template #text>
        <v-container
          v-if="scheduleStore.dictDetailEdit"
          fluid
          class="clean-space pa-2 ma-0 fill-height flex-column">
          <v-row class="w-100">
            <v-col cols="12">
              <v-text-field
                :model-value="scheduleStore.dictDetailEdit.name"
                label="Name"
                class="clean-space"
                density="compact"
                hide-details
                variant="plain"
                readonly></v-text-field>
            </v-col>
          </v-row>

          <v-container class="clean-space pl-3">
            <v-label class="mt-2 mb-3">Project:</v-label>
          </v-container>

          <v-row class="w-100">
            <v-col cols="8">
              <v-text-field
                :model-value="scheduleStore.dictDetailEdit.project_name"
                label="Name"
                variant="plain"
                class="clean-space"
                density="compact"
                hide-details
                readonly></v-text-field>
            </v-col>

            <v-col cols="4">
              <v-text-field
                :model-value="scheduleStore.dictDetailEdit.project_version"
                label="Version"
                variant="plain"
                class="clean-space"
                density="compact"
                hide-details
                readonly></v-text-field>
            </v-col>
          </v-row>
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolDeleting"
          @click="scheduleStore.showDeleteDialog = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="boolDeleting"
          :disabled="boolDeleting"
          @click="deleteSchedule()">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { loggerRenderer } from "../../Logging/logger";
import { useScheduleStore } from "../../Store/scheduleStore";
import { getErrorMessage } from "../../../../shared/error";

const scheduleStore = useScheduleStore();
const boolDeleting = ref(false);

async function deleteSchedule(): Promise<void> {
  if (boolDeleting.value || scheduleStore.dictDetailEdit === undefined) return;

  boolDeleting.value = true;
  try {
    await scheduleStore.deleteSchedule();
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to delete Schedule: ${getErrorMessage(e)}`);
  } finally {
    boolDeleting.value = false;
  }
}
</script>

<style scoped></style>
