<!-- FileName: SharedFileDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="620"
    aria-labelledby="file-delete-title">
    <v-card>
      <v-card-title id="file-delete-title">{{
        paths.length === 1 ? "Delete File" : "Delete Selected Files"
      }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
          {{ error.message }}
          <p v-if="error.statusCode === 0 || error.code === 'invalid_response'">
            The result is not confirmed. Retry to check the same deletion.
          </p>
        </v-alert>
        <p class="mb-3">
          Delete {{ paths.length }} {{ paths.length === 1 ? "file" : "files" }}? This cannot
          be undone.
        </p>
        <ul class="pl-5">
          <li v-for="path in paths" :key="path" class="file-path">{{ path }}</li>
        </ul>
      </v-card-text>
      <v-card-actions>
        <v-spacer /><v-btn :disabled="busy" @click="emit('close')">Cancel</v-btn>
        <v-btn
          color="error"
          variant="tonal"
          :loading="busy"
          :disabled="busy"
          @click="submit"
          >Delete</v-btn
        >
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "../stores/sessionStore";

import { getApiError, type ApiError } from "../api/errors";
import { deleteSharedFiles } from "../api/sharedFiles";
import type { FileDeleteResponse } from "../api/generated/browserApi";

const props = defineProps<{ paths: string[] }>();
const emit = defineEmits<{ close: []; deleted: [result: FileDeleteResponse] }>();
const session = useSessionStore();
const busy = ref(false);
const error = shallowRef<ApiError | null>(null);
let alive = true;
async function submit(): Promise<void> {
  if (busy.value || !session.session) return;
  busy.value = true;
  error.value = null;
  try {
    const result = await deleteSharedFiles(session.session.user.id, props.paths);
    if (alive) emit("deleted", result);
  } catch (e) {
    if (alive) error.value = getApiError(e);
  } finally {
    if (alive) busy.value = false;
  }
}
onBeforeUnmount(() => {
  alive = false;
});
</script>

<style scoped>
.file-path {
  overflow-wrap: anywhere;
}
</style>
