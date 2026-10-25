<!-- FileName: DataQueueDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolDeleting"
    scrollable
    max-width="560"
    aria-labelledby="queue-delete-title"
    @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title id="queue-delete-title">Delete Queue</v-card-title>

      <v-card-text ref="feedbackContainer">
        <p class="text-break mb-3">{{ queue.path }}</p>

        <p>
          Delete this queue and all
          {{ queue.unclaimed_count + queue.claimed_count }} items?
        </p>

        <v-alert
          v-if="error"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mt-4"
          role="alert">
          The operation was not confirmed. {{ error.message }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolDeleting"
          @click="emit('close')">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :disabled="boolDeleting || !queue.can_manage"
          :loading="boolDeleting"
          @click="submit">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { deleteQueue } from "@/api/dataQueues";
import type { QueueEntryResponse } from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{ queue: QueueEntryResponse }>();
const emit = defineEmits<{ close: []; deleted: [queue: QueueEntryResponse] }>();
const sessionStore = useSessionStore();

const error = shallowRef<ApiError | null>(null);
const boolDeleting = ref(false);
let boolUnmounted = false;

async function submit(): Promise<void> {
  if (boolDeleting.value || !props.queue.can_manage) return;
  boolDeleting.value = true;
  error.value = null;

  try {
    await deleteQueue(props.queue.id);
    if (!boolUnmounted) emit("deleted", props.queue);
  } catch (e) {
    if (!boolUnmounted) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolDeleting.value = false;
    if (!boolUnmounted && error.value) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
