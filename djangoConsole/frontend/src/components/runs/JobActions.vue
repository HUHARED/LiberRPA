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
    @click="openConfirm">
    <v-icon v-if="iconOnly" icon="mdi-close-circle-outline" />
    <template v-else>Close Job</template>
  </v-btn>

  <span
    v-if="job.stop_requested_at !== null && job.state !== JobState.Finished"
    class="text-body-2">
    Stop requested
  </span>

  <v-dialog v-model="boolConfirm" :persistent="boolBusy" max-width="600">
    <v-card>
      <v-card-title>Close Job</v-card-title>

      <v-card-text>
        <v-alert v-if="strCloseError" type="error" variant="tonal" class="mb-4">
          {{ strCloseError }}
        </v-alert>

        <p>
          Close this Job and cancel future attempts? The process may still be running; its
          result remains unconfirmed.
        </p>
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

import { controlJob, type JobControlAction, type JobInfo } from "@/api/runs";
import { JobState } from "@/api/generated/browserApi";
import { getApiError } from "@/api/errors";

const props = defineProps<{ job: JobInfo; iconOnly?: boolean }>();
const emit = defineEmits<{ updated: []; error: [message: string] }>();

const boolBusy = ref(false);
const boolConfirm = ref(false);
const strCloseError = ref("");

const strCancelLabel = computed(() =>
  props.job.state === JobState.WaitingRetry ? "Cancel Retries" : "Cancel",
);

function openConfirm(): void {
  strCloseError.value = "";
  boolConfirm.value = true;
}

async function act(action: JobControlAction): Promise<void> {
  if (boolBusy.value) return;

  strCloseError.value = "";
  boolBusy.value = true;

  try {
    await controlJob(props.job.id, action);
    boolConfirm.value = false;
    emit("updated");
  } catch (e) {
    if (action === "close") {
      strCloseError.value = getApiError(e).message;
    } else {
      emit("error", getApiError(e).message);
    }
  } finally {
    boolBusy.value = false;
  }
}
</script>

<style scoped></style>
