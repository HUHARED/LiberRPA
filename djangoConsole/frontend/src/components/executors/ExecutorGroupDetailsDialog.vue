<!-- FileName: ExecutorGroupDetailsDialog.vue -->
<template>
  <ExecutorGroupFormDialog
    v-if="editTarget"
    :group="editTarget"
    :departments="arrManagedDepartment"
    @close="editTarget = null"
    @saved="handleGroupSaved"
    @refresh="loadGroupDetails" />
  <v-dialog
    v-else
    :model-value="true"
    persistent
    scrollable
    max-width="1000"
    aria-labelledby="executor-group-details-title">
    <v-card :aria-busy="boolBusy">
      <v-card-title id="executor-group-details-title">
        {{ boolConfirmDelete ? "Delete Group" : "Group Details" }}
      </v-card-title>
      <v-progress-linear v-if="boolLoading" indeterminate color="primary" />
      <v-card-text>
        <v-alert
          v-if="strSuccessMessage"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ strSuccessMessage }}
        </v-alert>
        <v-alert
          v-for="warning in arrWarning"
          :key="warning.code"
          type="warning"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ warning.message }}
        </v-alert>
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
          <p v-if="groupInfo" class="mt-2">
            Previously loaded details are shown. Refresh to try again.
          </p>
        </v-alert>
        <v-alert v-if="deleteError" type="error" variant="tonal" class="mb-4" role="alert">
          Deletion was not confirmed. {{ deleteError.message }}
        </v-alert>
        <template v-if="groupInfo">
          <h2 class="text-subtitle-1 mb-3">Group Information</h2>
          <dl class="detail-fields mb-4">
            <div>
              <dt>Name</dt>
              <dd>{{ groupInfo.name }}</dd>
            </div>
            <div>
              <dt>Department</dt>
              <dd>{{ groupInfo.department.path }}</dd>
            </div>
            <template v-if="!boolConfirmDelete">
              <div>
                <dt>Members</dt>
                <dd>{{ groupInfo.member_count }}</dd>
              </div>
              <div>
                <dt>Online</dt>
                <dd>{{ groupInfo.online_count }}</dd>
              </div>
              <div>
                <dt>Created At ({{ strTimeZone }})</dt>
                <dd>{{ formatDateTime(groupInfo.created_at, strTimeZone) }}</dd>
              </div>
            </template>
          </dl>
          <template v-if="boolConfirmDelete">
            <p class="mb-2">This deletes the group and removes its member relationships.</p>
            <p>
              Executors, their client associations, and Console Dispatch settings are
              retained.
            </p>
          </template>
          <template v-else>
            <h2 class="text-subtitle-1 mb-2">Notes</h2>
            <p class="text-pre-wrap text-anywhere mb-4">{{ groupInfo.notes || "—" }}</p>
            <h2 class="text-subtitle-1 mb-2">Members</h2>
            <p class="mb-3">Member links open in a new tab.</p>
            <v-data-table
              :headers="ARR_MEMBER_HEADER"
              :items="groupInfo.members"
              :items-per-page="50"
              :items-per-page-options="[50]"
              :hide-default-footer="groupInfo.members.length <= 50"
              :mobile-breakpoint="600"
              item-value="id"
              disable-sort>
              <template #item.name="{ item }">
                <RouterLink
                  :to="{ name: 'executor-details', params: { executorId: item.id } }"
                  target="_blank"
                  rel="noopener"
                  class="d-inline-block table-text-narrow text-primary">
                  {{ item.name }}
                </RouterLink>
              </template>
              <template #item.account="{ item }">
                <div class="table-text-narrow">
                  {{
                    item.account
                      ? item.account.username
                        ? `${item.account.username} (${item.account.email})`
                        : item.account.email
                      : "—"
                  }}
                </div>
              </template>
              <template #item.association_status="{ item }">
                <span class="text-capitalize">{{ item.association_status }}</span>
              </template>
              <template #item.dispatch_enabled="{ item }">
                {{ item.dispatch_enabled ? "Enabled" : "Paused" }}
              </template>
              <template #no-data>This group has no members.</template>
            </v-data-table>
            <!-- TODO: Show referencing schedules when schedule queries are implemented. -->
          </template>
        </template>
      </v-card-text>
      <v-card-actions class="flex-wrap ga-2">
        <template v-if="boolConfirmDelete">
          <v-spacer />
          <v-btn variant="text" :disabled="boolBusy" @click="closeDelete">Cancel</v-btn>
          <v-btn
            color="error"
            variant="tonal"
            :loading="boolDeleting"
            :disabled="boolBusy || !boolCanManage"
            @click="submitDelete">
            Delete
          </v-btn>
        </template>
        <template v-else>
          <v-btn
            v-if="!boolDeleted"
            variant="text"
            :disabled="boolBusy"
            @click="loadGroupDetails">
            Refresh
          </v-btn>
          <v-btn
            v-if="boolCanManage"
            variant="tonal"
            :disabled="boolBusy"
            @click="openEdit">
            Edit
          </v-btn>
          <v-btn
            v-if="boolCanManage"
            color="error"
            variant="tonal"
            :disabled="boolBusy"
            @click="openDelete">
            Delete
          </v-btn>
          <v-spacer />
          <v-btn
            :to="{ name: 'executor-groups', query: route.query }"
            replace
            variant="text"
            :disabled="boolBusy">
            Close
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink, useRoute } from "vue-router";

import ExecutorGroupFormDialog from "./ExecutorGroupFormDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getExecutorGroupDetails, deleteExecutorGroup } from "@/api/executorGroups";
import type {
  ExecutorGroupRecordResponse,
  ExecutorGroupDetailsEntryResponse,
  ExecutorGroupWriteResponse,
  ExecutorGroupWarningResponse,
} from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ groupId: string }>();
const route = useRoute();
const emit = defineEmits<{ updated: []; deleted: [group: ExecutorGroupRecordResponse] }>();
const ARR_MEMBER_HEADER = [
  { title: "Name", key: "name", minWidth: 180 },
  { title: "Account", key: "account", minWidth: 220 },
  { title: "Association", key: "association_status", minWidth: 140 },
  { title: "Console Dispatch", key: "dispatch_enabled", minWidth: 170 },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const groupInfo = shallowRef<ExecutorGroupDetailsEntryResponse | null>(null);
const editTarget = shallowRef<ExecutorGroupDetailsEntryResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const deleteError = shallowRef<ApiError | null>(null);
const strSuccessMessage = ref("");
const arrWarning = shallowRef<ExecutorGroupWarningResponse[]>([]);
const boolLoading = ref(false);
const boolDeleting = ref(false);
const boolConfirmDelete = ref(false);
const boolDeleted = ref(false);
const boolBusy = computed(() => boolLoading.value || boolDeleting.value);
const arrManagedDepartment = computed(() =>
  (sessionStore.access?.departments ?? []).filter(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);
const boolCanManage = computed(
  () =>
    groupInfo.value?.can_manage &&
    arrManagedDepartment.value.some(
      (department) => department.id === groupInfo.value?.department_id,
    ),
);
let boolUnmounted = false;

async function loadGroupDetails(): Promise<void> {
  if (boolLoading.value || boolDeleted.value) return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getExecutorGroupDetails(props.groupId);
    if (boolUnmounted) return;
    groupInfo.value = response.executor_group;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      groupInfo.value = null;
      editTarget.value = null;
      boolConfirmDelete.value = false;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function openEdit(): void {
  if (!boolCanManage.value || boolBusy.value) return;
  strSuccessMessage.value = "";
  arrWarning.value = [];
  deleteError.value = null;
  editTarget.value = groupInfo.value;
}

async function handleGroupSaved(response: ExecutorGroupWriteResponse): Promise<void> {
  editTarget.value = null;
  // The write response confirms saved membership IDs; reload details before displaying member information.
  groupInfo.value = null;
  strSuccessMessage.value = "Group updated.";
  arrWarning.value = response.warnings;
  emit("updated");
  await loadGroupDetails();
}

function openDelete(): void {
  if (!boolCanManage.value || boolBusy.value) return;
  strSuccessMessage.value = "";
  arrWarning.value = [];
  deleteError.value = null;
  boolConfirmDelete.value = true;
}

function closeDelete(): void {
  if (boolBusy.value) return;
  deleteError.value = null;
  boolConfirmDelete.value = false;
}

async function submitDelete(): Promise<void> {
  if (!boolConfirmDelete.value || !boolCanManage.value || boolBusy.value) return;
  boolDeleting.value = true;
  deleteError.value = null;
  try {
    const response = await deleteExecutorGroup(props.groupId);
    if (boolUnmounted) return;
    groupInfo.value = null;
    boolConfirmDelete.value = false;
    boolDeleted.value = true;
    strSuccessMessage.value = `Group "${response.executor_group.name}" deleted.`;
    emit("deleted", response.executor_group);
  } catch (e) {
    if (boolUnmounted) return;
    deleteError.value = getApiError(e);
    if ([401, 403, 404].includes(deleteError.value.statusCode)) {
      if (deleteError.value.statusCode === 403) await sessionStore.refreshSession();
      if (!boolUnmounted) await loadGroupDetails();
    }
  } finally {
    boolDeleting.value = false;
  }
}

onMounted(() => void loadGroupDetails());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
