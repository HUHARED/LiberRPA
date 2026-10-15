<!-- FileName: ExecutorDetailsView.vue -->
<template>
  <v-btn to="/executors" variant="tonal" prepend-icon="mdi-arrow-left" class="mb-4">
    Back to Executors
  </v-btn>

  <v-row align="center" class="mb-4">
    <v-col>
      <h1 class="text-h5 mb-2 text-anywhere">
        {{ executorInfo?.name ?? "Executor Details" }}
      </h1>

      <p class="text-medium-emphasis">Executor Details</p>
    </v-col>

    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="!boolDeleted"
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolActionBlocked"
        @click="loadExecutorDetails">
        Refresh
      </v-btn>

      <v-btn
        v-if="executorInfo?.can_manage"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-pencil-outline"
        :disabled="boolActionBlocked"
        @click="openEdit">
        Edit
      </v-btn>

      <v-btn
        v-if="executorInfo?.can_manage"
        variant="tonal"
        :prepend-icon="executorInfo.dispatch_enabled ? 'mdi-pause' : 'mdi-play'"
        :loading="strPendingAction === 'dispatch'"
        :disabled="boolActionBlocked"
        @click="submitDispatch">
        {{ executorInfo.dispatch_enabled ? "Pause" : "Resume" }}
      </v-btn>

      <v-btn
        v-if="executorInfo?.can_manage"
        variant="tonal"
        prepend-icon="mdi-link-off"
        :disabled="boolActionBlocked || executorInfo.session_id === null"
        @click="openUnassociate">
        Unassociate
      </v-btn>

      <v-btn
        v-if="executorInfo?.can_manage"
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="boolActionBlocked"
        @click="openDelete">
        Delete
      </v-btn>
    </v-col>
  </v-row>

  <v-alert
    v-if="strSuccessMessage"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    {{ strSuccessMessage }}
  </v-alert>

  <v-alert v-if="dispatchError" type="error" variant="tonal" class="mb-4" role="alert">
    The dispatch change was not confirmed. {{ dispatchError.message }}
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
        <dl class="detail-fields">
          <div>
            <dt class="text-caption text-medium-emphasis">Name</dt>
            <dd>{{ executorInfo.name }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Department</dt>
            <dd>{{ executorInfo.department.path }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Association</dt>

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
            <dt class="text-caption text-medium-emphasis">Console Dispatch</dt>

            <dd>
              <v-chip
                size="small"
                variant="tonal"
                :color="executorInfo.dispatch_enabled ? 'primary' : 'warning'">
                {{ executorInfo.dispatch_enabled ? "Enabled" : "Paused" }}
              </v-chip>

              <p class="mt-2">
                Pausing does not stop running processes or remove the client association.
              </p>
            </dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Account</dt>

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
            <dt class="text-caption text-medium-emphasis">Computer</dt>
            <dd>{{ executorInfo.computer_name ?? "—" }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Version</dt>
            <dd>{{ executorInfo.client_version ?? "—" }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Last Seen</dt>
            <dd>{{ formatDateTime(executorInfo.last_seen_at, strTimeZone) }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Created At</dt>
            <dd>{{ formatDateTime(executorInfo.created_at, strTimeZone) }}</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Notes</v-card-title>

      <v-card-text class="text-pre-wrap text-anywhere">
        {{ executorInfo.notes || "—" }}
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Last Reported Work</v-card-title>

      <v-card-text>
        <p class="mb-3">
          Updated at {{ formatDateTime(executorInfo.last_work_reported_at, strTimeZone) }}.
          Counts describe the last report from the current associated client.
        </p>

        <v-table>
          <tbody>
            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">
                Other Active Runs
              </th>
              <td>{{ executorInfo.other_active_run_count ?? "Unknown" }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Console Running</th>
              <td>{{ executorInfo.central_running_count ?? "Unknown" }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Local Waiting</th>
              <td>{{ executorInfo.local_waiting_count ?? "Unknown" }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Referencing Schedules</v-card-title>

      <v-card-text>
        <p v-if="!executorInfo.referencing_schedules.length">No referencing schedules.</p>

        <v-table v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Enabled</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="schedule in executorInfo.referencing_schedules" :key="schedule.id">
              <td>
                <RouterLink
                  :to="{ name: 'schedule', params: { scheduleId: schedule.id } }"
                  class="text-primary text-decoration-none"
                  target="_blank"
                  rel="noopener">
                  {{ schedule.name }}
                </RouterLink>
              </td>
              <td>{{ schedule.enabled ? "Enabled" : "Disabled" }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card variant="outlined">
      <v-card-title>Executor Groups</v-card-title>

      <v-card-text>
        <ul v-if="executorInfo.executor_groups.length" class="pl-4">
          <li
            v-for="group in executorInfo.executor_groups"
            :key="group.id"
            class="text-anywhere">
            <RouterLink
              :to="{ name: 'executor-group-details', params: { groupId: group.id } }"
              target="_blank"
              rel="noopener"
              class="text-primary">
              {{ group.name }}
            </RouterLink>
          </li>
        </ul>

        <p v-else>This executor is not in any groups.</p>
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
            <p
              v-for="strMessage in editError.fields.__all__"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
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
          <v-btn
            variant="tonal"
            prepend-icon="mdi-close"
            :disabled="boolSaving"
            @click="closeEdit">
            Cancel
          </v-btn>
          <v-spacer />
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-content-save-outline"
            :loading="boolSaving"
            :disabled="boolLoading || !executorInfo?.can_manage">
            Save
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>

  <v-dialog
    :model-value="unassociateTarget !== null"
    persistent
    max-width="640"
    aria-labelledby="executor-unassociate-title">
    <v-card v-if="unassociateTarget">
      <v-card-title id="executor-unassociate-title">Unassociate Executor</v-card-title>

      <v-card-text>
        <v-alert
          v-if="unassociateError"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          Unassociation was not confirmed. {{ unassociateError.message }}
        </v-alert>

        <dl class="detail-fields mb-4">
          <div>
            <dt class="text-caption text-medium-emphasis">Executor</dt>
            <dd>{{ unassociateTarget.name }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Computer</dt>
            <dd>{{ unassociateTarget.computer_name ?? "—" }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Account</dt>

            <dd>
              {{
                unassociateTarget.account
                  ? unassociateTarget.account.username
                    ? `${unassociateTarget.account.username} (${unassociateTarget.account.email})`
                    : unassociateTarget.account.email
                  : "—"
              }}
            </dd>
          </div>
        </dl>

        <p class="mb-2">The selected client will lose its Console association.</p>

        <p class="mb-2">
          The Executor record, group and schedule references, and Console Dispatch setting
          are retained.
        </p>

        <p>This action does not stop running processes.</p>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="closeUnassociate">
          Cancel
        </v-btn>

        <v-btn
          v-if="unassociateError?.code === 'executor_association_changed'"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolBusy"
          @click="refreshUnassociateDetails">
          Refresh Details
        </v-btn>
        <v-spacer />
        <v-btn
          color="warning"
          variant="tonal"
          prepend-icon="mdi-link-off"
          :loading="strPendingAction === 'unassociate'"
          :disabled="
            boolBusy ||
            !executorInfo?.can_manage ||
            unassociateError?.code === 'executor_association_changed'
          "
          @click="submitUnassociate">
          Unassociate
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog
    :model-value="deleteTarget !== null"
    persistent
    max-width="640"
    aria-labelledby="executor-delete-title">
    <v-card v-if="deleteTarget">
      <v-card-title id="executor-delete-title">Delete Executor</v-card-title>

      <v-card-text>
        <v-alert v-if="deleteError" type="error" variant="tonal" class="mb-4" role="alert">
          Deletion was not confirmed. {{ deleteError.message }}
        </v-alert>

        <dl class="detail-fields mb-4">
          <div>
            <dt class="text-caption text-medium-emphasis">Executor</dt>
            <dd>{{ deleteTarget.name }}</dd>
          </div>

          <div>
            <dt class="text-caption text-medium-emphasis">Department</dt>
            <dd>{{ deleteTarget.department.path }}</dd>
          </div>
        </dl>

        <v-alert
          v-if="deleteTarget.executor_groups.length"
          type="warning"
          variant="tonal"
          class="mb-4">
          Remove this Executor from its groups before deleting it:
          <ul class="pl-4 mt-2">
            <li
              v-for="group in deleteTarget.executor_groups"
              :key="group.id"
              class="text-anywhere">
              <RouterLink
                :to="{ name: 'executor-group-details', params: { groupId: group.id } }"
                target="_blank"
                rel="noopener"
                class="text-primary">
                {{ group.name }}
              </RouterLink>
            </li>
          </ul>
        </v-alert>

        <p class="mb-2">
          This removes the Executor from Console and revokes any client association.
        </p>

        <p>Remote files are retained, and running processes are not stopped.</p>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="closeDelete">
          Cancel
        </v-btn>

        <v-btn
          v-if="
            deleteTarget.executor_groups.length ||
            deleteError?.code === 'executor_group_reference'
          "
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolBusy"
          @click="refreshDeleteDetails">
          Refresh Details
        </v-btn>
        <v-spacer />
        <v-btn
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="strPendingAction === 'delete'"
          :disabled="boolDeleteBlocked"
          @click="submitDelete">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  getExecutorDetails,
  deleteExecutor,
  updateExecutor,
  setExecutorDispatch,
  unassociateExecutor,
} from "@/api/executors";
import type { ExecutorDetailsEntryResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ executorId: string }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const executorInfo = shallowRef<ExecutorDetailsEntryResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const editError = shallowRef<ApiError | null>(null);
const dispatchError = shallowRef<ApiError | null>(null);
const unassociateError = shallowRef<ApiError | null>(null);
const unassociateTarget = shallowRef<ExecutorDetailsEntryResponse | null>(null);
const deleteError = shallowRef<ApiError | null>(null);
const deleteTarget = shallowRef<ExecutorDetailsEntryResponse | null>(null);
const boolLoading = ref(false);
const boolEditing = ref(false);
const boolDeleted = ref(false);
const strPendingAction = ref<"edit" | "dispatch" | "unassociate" | "delete" | null>(null);
const boolSaving = computed(() => strPendingAction.value === "edit");
const boolBusy = computed(() => boolLoading.value || strPendingAction.value !== null);

const boolActionBlocked = computed(
  () =>
    boolBusy.value ||
    boolEditing.value ||
    unassociateTarget.value !== null ||
    deleteTarget.value !== null,
);

const boolDeleteBlocked = computed(
  () =>
    boolBusy.value ||
    !executorInfo.value?.can_manage ||
    !deleteTarget.value ||
    deleteTarget.value.executor_groups.length > 0 ||
    deleteError.value?.code === "executor_group_reference",
);

const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
const strName = ref<string | null>("");
const strNotes = ref<string | null>("");
let intViewRevision = 0;

function closeEdit(): void {
  boolEditing.value = false;
  strName.value = "";
  strNotes.value = "";
  editError.value = null;
}

function closeUnassociate(): void {
  unassociateTarget.value = null;
  unassociateError.value = null;
}

function closeDelete(): void {
  deleteTarget.value = null;
  deleteError.value = null;
}

// TODO: Add job occupancy, preparation, and schedule references when their APIs are available.
async function loadExecutorDetails(): Promise<void> {
  if (boolDeleted.value) return;
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
      closeUnassociate();
      closeDelete();
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intViewRevision) boolLoading.value = false;
  }
}

function openEdit(): void {
  if (!executorInfo.value?.can_manage || boolActionBlocked.value) return;
  strName.value = executorInfo.value.name;
  strNotes.value = executorInfo.value.notes;
  editError.value = null;
  dispatchError.value = null;
  strSuccessMessage.value = "";
  boolEditing.value = true;
}

function validateName(value: string | null): true | string {
  return value?.trim() ? true : "Enter an executor name.";
}

async function submitEdit(event: SubmitEventPromise): Promise<void> {
  if (!boolEditing.value || boolBusy.value) return;
  const intCurrentRevision = intViewRevision;
  const validationResult = await event;
  if (
    !validationResult.valid ||
    !boolEditing.value ||
    boolBusy.value ||
    !executorInfo.value?.can_manage ||
    intCurrentRevision !== intViewRevision
  )
    return;
  strPendingAction.value = "edit";
  editError.value = null;
  try {
    const response = await updateExecutor(props.executorId, {
      name: (strName.value ?? "").trim(),
      notes: strNotes.value ?? "",
    });
    if (intCurrentRevision !== intViewRevision) return;
    executorInfo.value = { ...executorInfo.value, ...response.executor };
    closeEdit();
    strSuccessMessage.value = "Executor updated.";
    await loadExecutorDetails();
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    editError.value = getApiError(e);
    if ([401, 403, 404].includes(editError.value.statusCode)) await loadExecutorDetails();
  } finally {
    if (intCurrentRevision === intViewRevision) strPendingAction.value = null;
  }
}

async function submitDispatch(): Promise<void> {
  if (!executorInfo.value?.can_manage || boolActionBlocked.value) return;
  const intCurrentRevision = intViewRevision;
  const boolDispatchEnabled = !executorInfo.value.dispatch_enabled;
  strPendingAction.value = "dispatch";
  dispatchError.value = null;
  strSuccessMessage.value = "";
  try {
    const response = await setExecutorDispatch(props.executorId, boolDispatchEnabled);
    if (intCurrentRevision !== intViewRevision) return;
    executorInfo.value = { ...executorInfo.value, ...response.executor };
    strSuccessMessage.value = response.executor.dispatch_enabled
      ? "Console Dispatch enabled."
      : "Console Dispatch paused.";
    await loadExecutorDetails();
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    dispatchError.value = getApiError(e);
    if ([401, 403, 404].includes(dispatchError.value.statusCode))
      await loadExecutorDetails();
  } finally {
    if (intCurrentRevision === intViewRevision) strPendingAction.value = null;
  }
}

function openUnassociate(): void {
  if (
    !executorInfo.value?.can_manage ||
    !executorInfo.value.session_id ||
    boolActionBlocked.value
  )
    return;
  // Keep the reviewed association fixed until this dialog closes; retries must not target a replacement.
  unassociateTarget.value = executorInfo.value;
  unassociateError.value = null;
  dispatchError.value = null;
  strSuccessMessage.value = "";
}

function refreshUnassociateDetails(): void {
  if (boolBusy.value) return;
  closeUnassociate();
  void loadExecutorDetails();
}

async function submitUnassociate(): Promise<void> {
  const target = unassociateTarget.value;
  if (
    !target?.session_id ||
    !executorInfo.value?.can_manage ||
    boolBusy.value ||
    unassociateError.value?.code === "executor_association_changed"
  )
    return;
  const intCurrentRevision = intViewRevision;
  strPendingAction.value = "unassociate";
  unassociateError.value = null;
  try {
    const response = await unassociateExecutor(target.id, target.session_id);
    if (intCurrentRevision !== intViewRevision) return;
    executorInfo.value = {
      ...executorInfo.value,
      ...response.executor,
      association_status: "unassociated",
      session_id: null,
      account: null,
      computer_name: null,
      client_version: null,
      last_seen_at: null,
    };
    closeUnassociate();
    strSuccessMessage.value = "The selected client association was removed.";
    await loadExecutorDetails();
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    unassociateError.value = getApiError(e);
    if ([401, 403, 404].includes(unassociateError.value.statusCode))
      await loadExecutorDetails();
  } finally {
    if (intCurrentRevision === intViewRevision) strPendingAction.value = null;
  }
}

function openDelete(): void {
  if (!executorInfo.value?.can_manage || boolActionBlocked.value) return;
  deleteTarget.value = executorInfo.value;
  deleteError.value = null;
  dispatchError.value = null;
  strSuccessMessage.value = "";
}

function refreshDeleteDetails(): void {
  if (boolBusy.value) return;
  closeDelete();
  void loadExecutorDetails();
}

async function submitDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target || boolDeleteBlocked.value) return;
  const intCurrentRevision = intViewRevision;
  strPendingAction.value = "delete";
  deleteError.value = null;
  try {
    await deleteExecutor(target.id);
    if (intCurrentRevision !== intViewRevision) return;
    closeDelete();
    executorInfo.value = null;
    strUpdatedAt.value = null;
    requestError.value = null;
    boolDeleted.value = true;
    strSuccessMessage.value = `Executor "${target.name}" deleted.`;
  } catch (e) {
    if (intCurrentRevision !== intViewRevision) return;
    deleteError.value = getApiError(e);
    if ([401, 403, 404].includes(deleteError.value.statusCode)) await loadExecutorDetails();
  } finally {
    if (intCurrentRevision === intViewRevision) strPendingAction.value = null;
  }
}

watch(
  () => props.executorId,
  () => {
    // A response for a previously opened executor must not replace this page's data or draft.
    intViewRevision += 1;
    executorInfo.value = null;
    strUpdatedAt.value = null;
    strPendingAction.value = null;
    boolDeleted.value = false;
    strSuccessMessage.value = "";
    dispatchError.value = null;
    closeEdit();
    closeUnassociate();
    closeDelete();
    void loadExecutorDetails();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intViewRevision += 1;
});
</script>

<style scoped></style>
