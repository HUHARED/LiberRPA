<!-- FileName: PackageDeleteDialog.vue -->
<template>
  <v-dialog v-model="packageStore.showDeleteDialog" width="800px" height="400px">
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
            No Schedule uses this Package. A Package with a starting, running, or waiting
            Run still cannot be deleted.
          </v-container>
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          @click="packageStore.showDeleteDialog = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :disabled="packageStore.arrBoundSchedule.length !== 0"
          @click="deletePackage()">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { usePackageStore } from "../../Store/packageStore";

const emit = defineEmits<{ deleted: [] }>();
const packageStore = usePackageStore();

async function deletePackage(): Promise<void> {
  await packageStore.deletePackage();
  emit("deleted");
}
</script>

<style scoped></style>
