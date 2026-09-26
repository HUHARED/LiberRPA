<!-- FileName: ExecutorDetailsView.vue -->
<template>
  <v-btn to="/executors" variant="text" prepend-icon="mdi-arrow-left" class="mb-4">
    Back to Executors
  </v-btn>
  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2 executor-text">
        {{ executorInfo?.name ?? "Executor Details" }}
      </h1>
      <p class="text-body-2 text-medium-emphasis">Executor Details</p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolEditing || boolSaving"
        @click="loadExecutorDetails">
        Refresh
      </v-btn>
      <v-btn
        v-if="executorInfo?.can_manage"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-pencil-outline"
        :disabled="boolLoading || boolEditing || boolSaving"
        @click="openEdit">
        Edit
      </v-btn>
    </v-col>
  </v-row>
  <v-alert v-if="boolSaved" type="success" variant="tonal" class="mb-4" role="status">
    Executor updated.
  </v-alert>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{
      requestError.statusCode === 404
        ? "This executor does not exist or is not accessible to your account."
        : requestError.message
    }}
    <p v-if="executorInfo" class="mt-2">
      Previously loaded details are shown. Refresh to try again.
    </p>
  </v-alert>
  <v-progress-linear
    v-if="boolLoading"
    indeterminate
    color="primary"
    class="mb-4"
    aria-label="Loading executor details" />
  <template v-if="executorInfo">
    <div
      class="d-flex flex-wrap justify-space-between ga-2 mb-3 text-body-2 text-medium-emphasis">
      <span>Time zone: {{ strTimeZone }}</span>
      <span v-if="strUpdatedAt">
        Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
      </span>
    </div>
    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Executor Information</v-card-title>
      <v-card-text>
        <dl class="executor-fields">
          <div>
            <dt>Name</dt>
            <dd>{{ executorInfo.name }}</dd>
          </div>
          <div>
            <dt>Department</dt>
            <dd>{{ executorInfo.department.path }}</dd>
          </div>
          <div>
            <dt>Association</dt>
            <dd>
              <v-chip
                size="small"
                variant="tonal"
                class="text-capitalize"
                :color="
                  executorInfo.association_status === 'online'
                    ? 'success'
                    : executorInfo.association_status === 'offline'
                      ? 'warning'
                      : 'secondary'
                ">
                {{ executorInfo.association_status }}
              </v-chip>
            </dd>
          </div>
          <div>
            <dt>Console Dispatch</dt>
            <dd>
              <v-chip
                size="small"
                variant="tonal"
                :color="executorInfo.dispatch_enabled ? 'primary' : 'warning'">
                {{ executorInfo.dispatch_enabled ? "Enabled" : "Paused" }}
              </v-chip>
            </dd>
          </div>
          <div>
            <dt>Account</dt>
            <dd>
              {{
                executorInfo.account
                  ? executorInfo.account.username
                    ? `${executorInfo.account.username} (${executorInfo.account.email})`
                    : executorInfo.account.email
                  : "—"
              }}
            </dd>
          </div>
          <div>
            <dt>Computer</dt>
            <dd>{{ executorInfo.computer ?? "—" }}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{{ executorInfo.version ?? "—" }}</dd>
          </div>
          <div>
            <dt>Last Seen</dt>
            <dd>{{ formatDateTime(executorInfo.last_seen_at, strTimeZone) }}</dd>
          </div>
          <div>
            <dt>Created At</dt>
            <dd>{{ formatDateTime(executorInfo.created_at, strTimeZone) }}</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" class="mb-4">
      <v-card-title>Notes</v-card-title>
      <v-card-text class="executor-notes">{{ executorInfo.notes || "—" }}</v-card-text>
    </v-card>
    <v-card variant="outlined">
      <v-card-title>Executor Groups</v-card-title>
      <v-card-text>
        <ul v-if="executorInfo.executor_groups.length" class="pl-4">
          <li
            v-for="group in executorInfo.executor_groups"
            :key="group.id"
            class="executor-text">
            {{ group.name }}
          </li>
        </ul>
        <p v-else class="text-medium-emphasis">This executor is not in any groups.</p>
      </v-card-text>
    </v-card>
  </template>
  <v-dialog
    v-model="boolEditing"
    persistent
    max-width="640"
    aria-labelledby="executor-edit-title">
    <v-card>
      <v-card-title id="executor-edit-title">Edit Executor</v-card-title>
      <v-form validate-on="submit" @submit.prevent="submitEdit">
        <v-card-text>
          <v-alert v-if="editError" type="error" variant="tonal" class="mb-4" role="alert">
            Save was not confirmed. {{ editError.message }}
            <p v-for="message in editError.fields.__all__" :key="message" class="mt-2">
              {{ message }}
            </p>
          </v-alert>
          <v-text-field
            v-model="strName"
            label="Name"
            variant="outlined"
            density="compact"
            maxlength="128"
            :rules="[validateName]"
            :error-messages="editError?.fields.name ?? []"
            :disabled="boolSaving"
            required
            @update:model-value="editError = null" />
          <v-text-field
            :model-value="executorInfo?.department.path"
            label="Department"
            variant="plain"
            density="compact"
            hint="The department is fixed when the executor is created."
            persistent-hint
            readonly
            class="mb-4" />
          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="4"
            counter="2000"
            maxlength="2000"
            :error-messages="editError?.fields.notes ?? []"
            :disabled="boolSaving"
            @update:model-value="editError = null" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="boolSaving" @click="closeEdit">Cancel</v-btn>
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            :loading="boolSaving"
            :disabled="boolLoading || !executorInfo?.can_manage">
            Save
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getExecutorDetails, updateExecutor } from "../api/executors";
import type { ExecutorDetailsEntryResponse } from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

const props = defineProps<{ executorId: string }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const executorInfo = shallowRef<ExecutorDetailsEntryResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const editError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolEditing = ref(false);
const boolSaving = ref(false);
const boolSaved = ref(false);
const strUpdatedAt = ref<string | null>(null);
const strName = ref<string | null>("");
const strNotes = ref<string | null>("");
let intViewRevision = 0;

// TODO: Add job occupancy, preparation, and schedule references when their APIs are available.
async function loadExecutorDetails(): Promise<void> {
  const intCurrentRevision = intViewRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getExecutorDetails(props.executorId);
    if (intCurrentRevision !== intViewRevision) return;
    executorInfo.value = response.executor;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      executorInfo.value = null;
      strUpdatedAt.value = null;
      closeEdit();
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intViewRevision) boolLoading.value = false;
  }
}

function openEdit(): void {
  if (!executorInfo.value?.can_manage || boolLoading.value || boolSaving.value) return;
  strName.value = executorInfo.value.name;
  strNotes.value = executorInfo.value.notes;
  editError.value = null;
  boolSaved.value = false;
  boolEditing.value = true;
}

function closeEdit(): void {
  boolEditing.value = false;
  strName.value = "";
  strNotes.value = "";
  editError.value = null;
}

function validateName(value: string | null): true | string {
  return value?.trim() ? true : "Enter an executor name.";
}

async function submitEdit(event: SubmitEventPromise): Promise<void> {
  if (!boolEditing.value || boolSaving.value || boolLoading.value) return;
  const intCurrentRevision = intViewRevision;
  const validationResult = await event;
  if (
    !validationResult.valid ||
    !boolEditing.value ||
    boolSaving.value ||
    !executorInfo.value?.can_manage ||
    intCurrentRevision !== intViewRevision
  )
    return;
  boolSaving.value = true;
  editError.value = null;
  try {
    const response = await updateExecutor(props.executorId, {
      name: (strName.value ?? "").trim(),
      notes: strNotes.value ?? "",
    });
    if (intCurrentRevision !== intViewRevision) return;
    executorInfo.value = { ...executorInfo.value, ...response.executor };
    closeEdit();
    boolSaved.value = true;
    await loadExecutorDetails();
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    editError.value = getApiError(e);
    if ([401, 403, 404].includes(editError.value.statusCode)) await loadExecutorDetails();
  } finally {
    if (intCurrentRevision === intViewRevision) boolSaving.value = false;
  }
}

watch(
  () => props.executorId,
  () => {
    // A response for a previously opened executor must not replace this page's data or draft.
    intViewRevision += 1;
    executorInfo.value = null;
    strUpdatedAt.value = null;
    boolSaving.value = false;
    boolSaved.value = false;
    closeEdit();
    void loadExecutorDetails();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  intViewRevision += 1;
});
</script>

<style scoped>
.executor-text,
.executor-fields dd,
.executor-notes {
  overflow-wrap: anywhere;
}

.executor-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 20px;
}

.executor-fields dt {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  margin-bottom: 4px;
}

.executor-fields dd {
  margin: 0;
}

.executor-notes {
  white-space: pre-wrap;
}
</style>
