<!-- FileName: PackageDeleteDialog.vue -->
<template>
  <v-dialog
    v-model="packageStore.showDeleteDialog"
    width="800px"
    height="400px"
    :persistent="boolDeleting">
    <v-card title="Delete Package">
      <template #text>
        <v-container
          v-if="packageStore.dictDetailEdit"
          fluid
          class="clean-space pa-2 ma-0 fill-height flex-column">
          <v-row class="w-100" style="max-height: 60px">
            <v-col cols="9">
              <v-text-field
                :model-value="packageStore.dictDetailEdit.project_name"
                label="Project Name"
                class="clean-space"
                density="compact"
                hide-details
                variant="plain"
                readonly></v-text-field>
            </v-col>

            <v-col cols="3">
              <v-text-field
                :model-value="packageStore.dictDetailEdit.project_version"
                label="Project Version"
                variant="plain"
                class="clean-space"
                density="compact"
                hide-details
                readonly></v-text-field>
            </v-col>
          </v-row>

          <v-container
            v-if="packageStore.arrBoundSchedule.length !== 0"
            fluid
            class="border-thin flex-column-grow-1 flex-column">
            The following schedules use this package. Modify or delete them before deleting
            the package:
            <v-list
              :items="packageStore.arrBoundSchedule"
              class="clean-space w-100"
              style="width: max-content; flex: 1; min-width: 0px"
              density="compact"
              variant="flat"></v-list>
          </v-container>

          <v-container v-else fluid class="border-thin flex-column-grow-1 flex-column">
            Delete this Package?
          </v-container>
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolDeleting"
          @click="packageStore.showDeleteDialog = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="boolDeleting"
          :disabled="boolDeleting || packageStore.arrBoundSchedule.length !== 0"
          @click="deletePackage()">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { loggerRenderer } from "../../Logging/logger";
import { usePackageStore } from "../../Store/packageStore";
import { getErrorMessage } from "../../../../shared/error";

const emit = defineEmits<{ deleted: [] }>();
const packageStore = usePackageStore();
const boolDeleting = ref(false);

async function deletePackage(): Promise<void> {
  if (
    boolDeleting.value ||
    packageStore.dictDetailEdit === undefined ||
    packageStore.arrBoundSchedule.length !== 0
  )
    return;

  boolDeleting.value = true;
  try {
    await packageStore.deletePackage();
    emit("deleted");
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to delete Package: ${getErrorMessage(e)}`);
  } finally {
    boolDeleting.value = false;
  }
}
</script>

<style scoped></style>
