<!-- FileName: ScheduleDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolDeleting"
    max-width="560"
    aria-labelledby="schedule-delete-title"
    @update:model-value="!$event && emit('close')">
    <v-card ref="feedbackContainer">
      <v-card-title id="schedule-delete-title">Delete Schedule</v-card-title>

      <v-card-text>
        <p>
          Delete
          <span class="font-weight-bold">{{ schedule.name }}</span>
          ? Future triggers will stop. Already accepted Jobs continue independently,
          including waiting and retries.
        </p>

        <v-alert
          v-if="strError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mt-4"
          role="alert">
          {{ strError }}
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
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          color="error"
          :loading="boolDeleting"
          :disabled="boolDeleting || !schedule.can_manage"
          @click="submit">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from "vue";

import { getApiError } from "@/api/errors";
import { type ScheduleListEntry, deleteSchedule } from "@/api/schedules";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{ schedule: ScheduleListEntry }>();
const emit = defineEmits<{ close: []; deleted: [] }>();

const boolDeleting = ref(false);
const strError = ref("");
let boolUnmounted = false;

async function submit(): Promise<void> {
  if (boolDeleting.value || !props.schedule.can_manage) return;
  boolDeleting.value = true;
  strError.value = "";

  try {
    await deleteSchedule(props.schedule.id);
    if (!boolUnmounted) emit("deleted");
  } catch (e) {
    if (!boolUnmounted) strError.value = getApiError(e).message;
  } finally {
    boolDeleting.value = false;
    if (!boolUnmounted && strError.value) {
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
