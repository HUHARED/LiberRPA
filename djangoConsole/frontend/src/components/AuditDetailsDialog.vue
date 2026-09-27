<!-- FileName: AuditDetailsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="1000"
    aria-labelledby="audit-details-title">
    <v-card :aria-busy="boolLoading">
      <v-card-title id="audit-details-title">Audit Details</v-card-title>
      <v-progress-linear v-if="boolLoading" indeterminate color="primary" />
      <v-card-text>
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
          <div v-if="![401, 403, 404].includes(requestError.statusCode)" class="mt-3">
            <v-btn variant="outlined" :disabled="boolLoading" @click="loadDetails"
              >Retry</v-btn
            >
          </div>
        </v-alert>
        <template v-if="record">
          <dl class="detail-fields">
            <dt>Time ({{ strTimeZone }})</dt>
            <dd>{{ formatDateTime(record.created_at, strTimeZone) }}</dd>
            <dt>Actor</dt>
            <dd>{{ record.actor_name }}</dd>
            <template v-if="record.actor_id">
              <dt>Actor ID</dt>
              <dd>{{ record.actor_id }}</dd>
            </template>
            <dt>Channel</dt>
            <dd>{{ AUDIT_CHANNEL_LABEL[record.channel] }}</dd>
            <dt>Module</dt>
            <dd>{{ formatAuditLabel(record.module) }}</dd>
            <dt>Action</dt>
            <dd>{{ record.action }}</dd>
            <dt>Object Type</dt>
            <dd>{{ formatAuditLabel(record.object_type) }}</dd>
            <dt>Object</dt>
            <dd>{{ record.object_name || "—" }}</dd>
            <dt>Object ID</dt>
            <dd>{{ record.object_id || "—" }}</dd>
            <dt>Organization</dt>
            <dd>{{ record.organization_name }}</dd>
            <template v-if="record.department_id">
              <dt>Department ID</dt>
              <dd>{{ record.department_id }}</dd>
            </template>
            <dt>Result</dt>
            <dd>{{ formatAuditLabel(record.result) }}</dd>
            <dt>Stage</dt>
            <dd>{{ formatAuditLabel(record.stage) }}</dd>
            <template v-if="record.request_id">
              <dt>Request ID</dt>
              <dd>{{ record.request_id }}</dd>
            </template>
            <dt>Audit ID</dt>
            <dd>{{ record.id }}</dd>
          </dl>
          <v-divider class="my-4" />
          <h3 class="text-subtitle-1 mb-2">Summary</h3>
          <p>
            {{ formatAuditLabel(record.action) }} — {{ record.stage }} {{ record.result }}.
          </p>
          <dl
            v-if="record.reason_code || record.http_status !== null"
            class="detail-fields mt-4">
            <template v-if="record.reason_code">
              <dt>
                {{ record.result === "failed" ? "Failure Reason Code" : "Reason Code" }}
              </dt>
              <dd>{{ record.reason_code }}</dd>
            </template>
            <template v-if="record.http_status !== null">
              <dt>HTTP Status</dt>
              <dd>{{ record.http_status }}</dd>
            </template>
          </dl>
          <template v-if="record.changes.length">
            <v-divider class="my-4" />
            <h3 class="text-subtitle-1 mb-2">Changes</h3>
            <v-alert v-if="record.details_omitted" type="info" variant="tonal" class="mb-4">
              This record exceeded the audit detail size limit. Only changed field names
              were retained.
            </v-alert>
            <v-table>
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Before</th>
                  <th scope="col">After</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="change in record.changes" :key="change.field">
                  <td>{{ formatAuditLabel(change.field) }}</td>
                  <td class="text-pre-wrap text-anywhere">
                    {{ formatChangeValue(change.before) }}
                  </td>
                  <td class="text-pre-wrap text-anywhere">
                    {{ formatChangeValue(change.after) }}
                  </td>
                </tr>
              </tbody>
            </v-table>
            <p v-if="boolValuesOmitted" class="mt-3 text-medium-emphasis">
              “Not recorded” means the field changed but its content was not stored, as with
              Notes.
            </p>
          </template>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('close')">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getAuditDetails } from "../api/audit";
import type { AuditDetailsRecordResponse } from "../api/generated/browserApi";
import { AUDIT_CHANNEL_LABEL, formatAuditLabel } from "../app/audit";
import { formatDateTime } from "../app/navigation";

const props = defineProps<{ auditId: string }>();
const emit = defineEmits<{ close: [] }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const record = shallowRef<AuditDetailsRecordResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolValuesOmitted = computed(() =>
  record.value?.changes.some((change) => change.before === null || change.after === null),
);
let boolUnmounted = false;

function formatChangeValue(value: string | null): string {
  return value === null ? "Not recorded" : value === "" ? "(empty)" : value;
}

async function loadDetails(): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getAuditDetails(props.auditId);
    if (boolUnmounted) return;
    record.value = response.record;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

onMounted(() => void loadDetails());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
