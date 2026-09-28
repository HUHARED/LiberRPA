<!-- FileName: QueueItemDetailsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="900"
    aria-labelledby="queue-item-title"
    ><v-card>
      <v-card-title id="queue-item-title">Item Details</v-card-title>
      <v-card-text>
        <v-progress-linear v-if="loading" indeterminate class="mb-4" />
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">{{
          error.statusCode === 404
            ? "The item no longer exists or is unavailable."
            : error.message
        }}</v-alert>
        <v-alert
          v-if="strActionError"
          type="error"
          variant="tonal"
          closable
          class="mb-4"
          role="alert"
          @click:close="strActionError = ''">
          {{ strActionError }}
        </v-alert>
        <v-alert v-if="message" type="success" variant="tonal" class="mb-4" role="status">{{
          message
        }}</v-alert>
        <template v-if="item"
          ><dl class="detail-fields">
            <div class="full-width-field">
              <dt>Item ID</dt>
              <dd>{{ item.id }}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{{ item.status === "claimed" ? "Claimed" : "Unclaimed" }}</dd>
            </div>
            <div>
              <dt>Uploaded By</dt>
              <dd>{{ item.uploaded_by_name }}</dd>
            </div>
            <div>
              <dt>Uploaded At ({{ timeZone }})</dt>
              <dd>{{ formatDateTime(item.uploaded_at, timeZone) }}</dd>
            </div>
            <div>
              <dt>Last Claimed By</dt>
              <dd>{{ item.last_claimed_by_name || "—" }}</dd>
            </div>
            <div>
              <dt>Last Claimed At ({{ timeZone }})</dt>
              <dd>{{ formatDateTime(item.last_claimed_at, timeZone) }}</dd>
            </div>
          </dl>
          <v-textarea
            :model-value="json"
            label="Data (JSON)"
            variant="outlined"
            readonly
            rows="12"
            class="mt-5"
            hide-details
        /></template>
      </v-card-text>
      <v-card-actions
        ><v-btn v-if="error" variant="text" :disabled="loading" @click="load">Retry</v-btn
        ><v-btn variant="tonal" :disabled="loading || !item || !!error" @click="copyJson"
          >Copy JSON</v-btn
        ><v-spacer /><v-btn
          :to="{ name: 'data-queue-details', params: { queueId }, query: route.query }"
          replace
          variant="text"
          >Close</v-btn
        ></v-card-actions
      >
    </v-card></v-dialog
  >
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useRoute } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getQueueItem } from "../api/dataQueues";
import type { QueueItemDetailsResponse } from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const props = defineProps<{ queueId: string; itemId: string }>();
const route = useRoute();
const session = useSessionStore();
const timeZone = computed(() => session.session?.user.time_zone ?? "UTC");
const item = shallowRef<QueueItemDetailsResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const message = ref("");
const strActionError = ref("");
const loading = ref(false);
const json = computed(() => (item.value ? JSON.stringify(item.value.data, null, 2) : ""));
let unmounted = false;
async function load(): Promise<void> {
  if (loading.value) return;
  loading.value = true;
  error.value = null;
  strActionError.value = "";
  item.value = null;
  try {
    const response = await getQueueItem(props.queueId, props.itemId);
    if (!unmounted) item.value = response;
  } catch (e) {
    if (!unmounted) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    loading.value = false;
  }
}
async function copyJson(): Promise<void> {
  strActionError.value = "";
  message.value = "";
  try {
    await navigator.clipboard.writeText(json.value);
    if (!unmounted) message.value = "JSON copied.";
  } catch {
    if (!unmounted)
      strActionError.value = "The JSON could not be copied. Copy it from the Data field.";
  }
}

onMounted(() => void load());
onBeforeUnmount(() => {
  unmounted = true;
});
</script>

<style scoped></style>
