<!-- FileName: AuditDetailsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    scrollable
    max-width="1000"
    aria-labelledby="audit-details-title"
    @update:model-value="!$event && emit('close')">
    <v-card :aria-busy="boolLoading">
      <v-card-title id="audit-details-title">Audit Details</v-card-title>
      <v-progress-linear v-if="boolLoading" indeterminate color="primary" />

      <v-card-text>
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
          <div v-if="![401, 403, 404].includes(requestError.statusCode)" class="mt-3">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              :disabled="boolLoading"
              @click="loadDetails">
              Retry
            </v-btn>
          </div>
        </v-alert>

        <template v-if="record">
          <dl class="detail-fields">
            <div>
              <dt class="text-caption text-medium-emphasis">Time</dt>
              <dd>{{ formatDateTime(record.created_at, strTimeZone) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Actor</dt>
              <dd>{{ record.actor_name }}</dd>
            </div>

            <div v-if="record.actor_id">
              <dt class="text-caption text-medium-emphasis">Actor ID</dt>
              <dd>{{ record.actor_id }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Channel</dt>
              <dd>{{ AUDIT_CHANNEL_LABEL[record.channel] }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Module</dt>
              <dd>
                {{ formatAuditLabel(record.action.slice(0, record.action.indexOf("."))) }}
              </dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Action</dt>
              <dd>{{ AUDIT_ACTION_LABEL[record.action] }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Object Type</dt>
              <dd>{{ formatAuditLabel(record.object_type) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Object</dt>

              <dd>
                {{ record.object_name || "—" }}
              </dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Object ID</dt>
              <dd>{{ record.object_id || "—" }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Organization</dt>

              <dd>
                {{
                  record.organization_id
                    ? record.organization_name || "Unknown organization"
                    : "—"
                }}
              </dd>
            </div>

            <div v-if="record.organization_id">
              <dt class="text-caption text-medium-emphasis">Organization ID</dt>
              <dd>{{ record.organization_id }}</dd>
            </div>

            <div v-if="record.department_id">
              <dt class="text-caption text-medium-emphasis">Department ID</dt>
              <dd>{{ record.department_id }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Result</dt>
              <dd class="font-weight-bold">{{ formatAuditLabel(record.result) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Stage</dt>
              <dd>{{ formatAuditLabel(record.stage) }}</dd>
            </div>

            <div v-if="record.request_id">
              <dt class="text-caption text-medium-emphasis">Request ID</dt>
              <dd>{{ record.request_id }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Audit ID</dt>
              <dd>{{ record.id }}</dd>
            </div>
          </dl>

          <dl
            v-if="record.reason || record.reason_code || record.http_status !== null"
            class="detail-fields mt-4">
            <div v-if="record.reason">
              <dt class="text-caption text-medium-emphasis">
                {{ record.result === "failed" ? "Failure Reason" : "Reason" }}
              </dt>
              <dd class="text-pre-wrap text-anywhere">{{ record.reason }}</dd>
            </div>

            <div v-if="record.reason_code">
              <dt class="text-caption text-medium-emphasis">
                {{ record.result === "failed" ? "Failure Reason Code" : "Reason Code" }}
              </dt>

              <dd>{{ record.reason_code }}</dd>
            </div>

            <div v-if="record.http_status !== null">
              <dt class="text-caption text-medium-emphasis">HTTP Status</dt>
              <dd>{{ record.http_status }}</dd>
            </div>
          </dl>

          <v-alert v-if="record.details_omitted" type="info" variant="tonal" class="mt-4">
            Some details were not retained because this record exceeded the audit detail
            size limit.
          </v-alert>

          <template v-if="record.changes.length">
            <v-divider class="my-4" />

            <h3 class="text-subtitle-1 mb-2">Changes</h3>

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
                    {{ formatChangeValue(change.field, change.before) }}
                  </td>
                  <td class="text-pre-wrap text-anywhere">
                    {{ formatChangeValue(change.field, change.after) }}
                  </td>
                </tr>
              </tbody>
            </v-table>

            <p v-if="boolValuesOmitted" class="mt-3 text-medium-emphasis">
              "Not recorded" means the field changed but its content was not stored, as with
              Notes.
            </p>
          </template>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('close')">Close</v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getAuditDetails } from "@/api/audit";
import {
  AUDIT_ACTION_LABEL,
  type AuditDetailsRecordResponse,
} from "@/api/generated/browserApi";

import { AUDIT_CHANNEL_LABEL, formatAuditLabel } from "@/app/audit";
import { formatDateTime } from "@/app/formatters";

const SET_DATE_TIME_FIELD = new Set([
  "expires_at",
  "revoked_at",
  "suspended_at",
  "deletion_requested_at",
  "deletion_due_at",
  "deletion_started_at",
  "deleted_at",
  "accepted_at",
  "entered_at",
  "active_from",
  "active_until",
]);

const props = withDefaults(defineProps<{ auditId: string; platform?: boolean }>(), {
  platform: false,
});
const emit = defineEmits<{ close: [] }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const record = shallowRef<AuditDetailsRecordResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);

const boolValuesOmitted = computed(() =>
  record.value?.changes.some((change) => change.before === null || change.after === null),
);

let intDetailsRevision = 0;

function formatChangeValue(field: string, value: string | null): string {
  if (value === null) return "Not recorded";
  if (value === "") return "(empty)";
  if (value !== "null" && SET_DATE_TIME_FIELD.has(field))
    return formatDateTime(value, strTimeZone.value);
  return value;
}

async function loadDetails(): Promise<void> {
  const intCurrentRevision = ++intDetailsRevision;
  boolLoading.value = true;
  record.value = null;
  requestError.value = null;
  try {
    const response = await getAuditDetails(props.auditId, props.platform);
    if (intCurrentRevision !== intDetailsRevision) return;
    record.value = response.record;
  } catch (e) {
    if (intCurrentRevision !== intDetailsRevision) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    if (intCurrentRevision === intDetailsRevision) boolLoading.value = false;
  }
}

watch([() => props.auditId, () => props.platform], () => void loadDetails(), {
  immediate: true,
});

onBeforeUnmount(() => {
  intDetailsRevision += 1;
});
</script>

<style scoped></style>
