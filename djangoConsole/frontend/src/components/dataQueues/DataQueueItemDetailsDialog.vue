<!-- FileName: DataQueueItemDetailsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    scrollable
    max-width="900"
    aria-labelledby="queue-item-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="queue-item-title">Item Details</v-card-title>

      <v-card-text>
        <v-progress-linear v-if="boolLoading" indeterminate class="mb-4" />

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
          {{
            error.statusCode === 404
              ? "The item no longer exists or is unavailable."
              : error.message
          }}
        </v-alert>

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

        <v-alert
          v-if="strMessage"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ strMessage }}
        </v-alert>

        <template v-if="item">
          <dl class="detail-fields">
            <div class="full-width-field">
              <dt class="text-caption text-medium-emphasis">Item ID</dt>
              <dd>{{ item.id }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Status</dt>
              <dd>{{ item.status === "claimed" ? "Claimed" : "Unclaimed" }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Uploaded By</dt>
              <dd>{{ item.uploaded_by_name }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Uploaded At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(item.uploaded_at, strTimeZone) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Last Claimed By</dt>
              <dd>{{ item.last_claimed_by_name || "—" }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Last Claimed At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(item.last_claimed_at, strTimeZone) }}</dd>
            </div>
          </dl>

          <v-textarea
            :model-value="strJson"
            label="Data (JSON)"
            variant="outlined"
            readonly
            rows="12"
            class="mt-5"
            hide-details />
        </template>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="closeDialog">Close</v-btn>

        <v-btn
          v-if="error"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolLoading"
          @click="load">
          Retry
        </v-btn>

        <v-btn
          variant="tonal"
          prepend-icon="mdi-content-copy"
          :disabled="boolLoading || !item || !!error"
          @click="copyJson">
          Copy JSON
        </v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getQueueItem } from "@/api/dataQueues";
import type { QueueItemDetailsResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ queueId: string; itemId: string }>();
const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const item = shallowRef<QueueItemDetailsResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const strMessage = ref("");
const strActionError = ref("");
const boolLoading = ref(false);

const strJson = computed(() =>
  item.value ? JSON.stringify(item.value.data, null, 2) : "",
);

let boolUnmounted = false;

async function load(): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  error.value = null;
  strActionError.value = "";
  item.value = null;
  try {
    const response = await getQueueItem(props.queueId, props.itemId);
    if (!boolUnmounted) item.value = response;
  } catch (e) {
    if (!boolUnmounted) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function closeDialog(): void {
  void router.replace({
    name: "data-queue-details",
    params: { queueId: props.queueId },
    query: route.query,
  });
}

async function copyJson(): Promise<void> {
  strActionError.value = "";
  strMessage.value = "";
  try {
    await navigator.clipboard.writeText(strJson.value);
    if (!boolUnmounted) strMessage.value = "JSON copied.";
  } catch {
    if (!boolUnmounted)
      strActionError.value = "The JSON could not be copied. Copy it from the Data field.";
  }
}

onMounted(() => void load());

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
