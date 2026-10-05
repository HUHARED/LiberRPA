<!-- FileName: JobActions.vue -->
<template>
  <v-btn
    v-if="job.can_cancel"
    size="small"
    variant="text"
    :loading="boolBusy"
    @click="act('cancel')">
    {{ job.state === "waiting_retry" ? "Cancel Retries" : "Cancel" }}
  </v-btn>
  <v-btn
    v-if="job.can_stop"
    size="small"
    variant="text"
    color="warning"
    :loading="boolBusy"
    @click="act('stop')">
    Stop
  </v-btn>
  <v-btn
    v-if="job.can_close"
    size="small"
    variant="text"
    color="error"
    :disabled="boolBusy"
    @click="boolConfirm = true">
    Close Job
  </v-btn>
  <span v-if="job.state === 'stopping'" class="text-body-2">Stop requested</span>
  <v-dialog v-model="boolConfirm" persistent max-width="600">
    <v-card>
      <v-card-title>Close Job</v-card-title>
      <v-card-text>
        Close this Job and cancel future attempts? The process may still be running; its
        result remains unconfirmed.
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolBusy" @click="boolConfirm = false">Cancel</v-btn>
        <v-btn color="error" :loading="boolBusy" @click="act('close')">Close Job</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { controlJob, type JobInfo } from "@/api/runs";
import { getApiError } from "@/api/errors";
const props = defineProps<{ job: JobInfo }>();
const emit = defineEmits<{ updated: []; error: [message: string] }>();
const boolBusy = ref(false);
const boolConfirm = ref(false);
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
