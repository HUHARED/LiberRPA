<!-- FileName: JobActions.vue -->
<template>
  <v-btn
    v-if="job.can_cancel"
    v-tooltip:bottom="iconOnly ? strCancelLabel : undefined"
    :icon="iconOnly"
    :aria-label="strCancelLabel"
    size="small"
    :variant="iconOnly ? 'text' : 'tonal'"
    :prepend-icon="iconOnly ? undefined : 'mdi-cancel'"
    :loading="boolBusy"
    @click="act('cancel')">
    <v-icon v-if="iconOnly" icon="mdi-cancel" />
    <template v-else>{{ strCancelLabel }}</template>
  </v-btn>

  <v-btn
    v-if="job.can_stop"
    v-tooltip:bottom="iconOnly ? 'Stop' : undefined"
    :icon="iconOnly"
    aria-label="Stop"
    size="small"
    :variant="iconOnly ? 'text' : 'tonal'"
    :prepend-icon="iconOnly ? undefined : 'mdi-stop-circle-outline'"
    color="warning"
    :loading="boolBusy"
    @click="act('stop')">
    <v-icon v-if="iconOnly" icon="mdi-stop-circle-outline" />
    <template v-else>Stop</template>
  </v-btn>

  <v-btn
    v-if="job.can_close"
    v-tooltip:bottom="iconOnly ? 'Close Job' : undefined"
    :icon="iconOnly"
    aria-label="Close Job"
    size="small"
    :variant="iconOnly ? 'text' : 'tonal'"
    :prepend-icon="iconOnly ? undefined : 'mdi-close-circle-outline'"
    color="error"
    :disabled="boolBusy"
    @click="boolConfirm = true">
    <v-icon v-if="iconOnly" icon="mdi-close-circle-outline" />
    <template v-else>Close Job</template>
  </v-btn>
  <span v-if="job.state === JobState.Stopping" class="text-body-2">Stop requested</span>
  <v-dialog v-model="boolConfirm" persistent max-width="600">
    <v-card>
      <v-card-title>Close Job</v-card-title>

      <v-card-text>
        Close this Job and cancel future attempts? The process may still be running; its
        result remains unconfirmed.
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="boolConfirm = false">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close-circle-outline"
          color="error"
          :loading="boolBusy"
          @click="act('close')">
          Close Job
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { controlJob, JobState, type JobInfo } from "@/api/runs";
import { getApiError } from "@/api/errors";

const props = defineProps<{ job: JobInfo; iconOnly?: boolean }>();
const emit = defineEmits<{ updated: []; error: [message: string] }>();
const boolBusy = ref(false);
const boolConfirm = ref(false);

const strCancelLabel = computed(() =>
  props.job.state === JobState.WaitingRetry ? "Cancel Retries" : "Cancel",
);

async function act(action: "cancel" | "stop" | "close"): Promise<void> {
  boolBusy.value = true;
  try {
    await controlJob(props.job.id, action);
    boolConfirm.value = false;
    emit("updated");
  } catch (e) {
    emit("error", getApiError(e).message);
  } finally {
    boolBusy.value = false;
  }
}
</script>

<style scoped></style>
