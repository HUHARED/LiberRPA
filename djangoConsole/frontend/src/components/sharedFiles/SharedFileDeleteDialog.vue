<!-- FileName: SharedFileDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="620"
    aria-labelledby="file-delete-title">
    <v-card>
      <v-card-title id="file-delete-title">
        {{ paths.length === 1 ? "Delete File" : "Delete Selected Files" }}
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
          {{ error.message }}
          <p v-if="error.statusCode === 0 || error.code === 'invalid_response'">
            The result is not confirmed. Retry to check the same deletion.
          </p>
        </v-alert>
        <p class="mb-3">
          Delete
          <span class="font-weight-bold">{{ paths.length }}</span>
          {{ paths.length === 1 ? "file" : "files" }}? This cannot be undone.
        </p>
        <ul class="pl-5">
          <li
            v-for="strPath in paths"
            :key="strPath"
            class="file-path text-highlight font-weight-bold">
            {{ strPath }}
          </li>
        </ul>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="emit('close')">Cancel</v-btn>
        <v-btn
          color="error"
          variant="tonal"
          :loading="boolBusy"
          :disabled="boolBusy"
          @click="submit">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { getApiError, type ApiError } from "@/api/errors";
import { deleteSharedFiles } from "@/api/sharedFiles";
import type { FileDeleteResponse } from "@/api/generated/browserApi";

const props = defineProps<{ paths: string[] }>();
const emit = defineEmits<{ close: []; deleted: [result: FileDeleteResponse] }>();
const sessionStore = useSessionStore();
const boolBusy = ref(false);
const error = shallowRef<ApiError | null>(null);
let boolAlive = true;
async function submit(): Promise<void> {
  if (boolBusy.value || !sessionStore.session) return;
  boolBusy.value = true;
  error.value = null;
  try {
    const result = await deleteSharedFiles(sessionStore.session.user.id, props.paths);
    if (boolAlive) emit("deleted", result);
  } catch (e) {
    if (boolAlive) error.value = getApiError(e);
  } finally {
    if (boolAlive) boolBusy.value = false;
  }
}
onBeforeUnmount(() => {
  boolAlive = false;
});
</script>

<style scoped>
.file-path {
  overflow-wrap: anywhere;
}
</style>
