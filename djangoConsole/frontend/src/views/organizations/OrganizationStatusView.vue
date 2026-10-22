<!-- FileName: OrganizationStatusView.vue -->
<template>
  <v-card variant="outlined" class="mx-auto mt-4" max-width="640" aria-live="polite">
    <v-card-text>
      <v-icon icon="mdi-office-building-outline" size="40" color="primary" class="mb-4" />
      <p class="text-medium-emphasis mb-2">
        {{ sessionStore.access?.organization.name ?? "Workspace status" }}
      </p>

      <h1 class="text-h5 mb-4">{{ strTitle }}</h1>
      <p class="text-body-1 mb-4">{{ strDescription }}</p>

      <v-alert
        v-if="sessionStore.access?.organization.deletion_due_at"
        type="info"
        variant="tonal"
        title="Scheduled deletion"
        :text="
          formatDateTime(sessionStore.access.organization.deletion_due_at, strTimeZone)
        "
        class="mb-4" />

      <v-alert
        v-if="
          sessionStore.access?.organization.suspended_at &&
          sessionStore.access.organization.deletion_requested_at
        "
        type="warning"
        variant="tonal"
        class="mb-4">
        This organization is also suspended. Canceling deletion will not lift the
        suspension.
      </v-alert>

      <v-alert v-if="requestError" type="error" variant="tonal" role="alert">
        {{ requestError.message }}
      </v-alert>
    </v-card-text>

    <v-card-actions class="px-4 pb-4 flex-wrap ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-logout"
        :loading="sessionStore.busy"
        :disabled="boolActionBlocked"
        @click="submitSignOut">
        Sign Out
      </v-btn>
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolRefreshing"
        :disabled="boolActionBlocked"
        @click="refreshStatus">
        Refresh Status
      </v-btn>

      <v-btn
        v-if="boolCanCancel"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-undo"
        :disabled="boolActionBlocked"
        @click="boolShowCancellation = true">
        Cancel Deletion
      </v-btn>
    </v-card-actions>
  </v-card>

  <OrganizationDeletionCancelDialog
    v-if="boolShowCancellation && boolCanCancel"
    @close="boolShowCancellation = false" />
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";

import OrganizationDeletionCancelDialog from "@/components/organizations/OrganizationDeletionCancelDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";

import { formatDateTime } from "@/app/formatters";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolRefreshing = ref(false);
const boolShowCancellation = ref(false);
const boolCanCancel = computed(
  () =>
    sessionStore.access?.is_org_admin &&
    sessionStore.access.organization.deletion_requested_at !== null &&
    sessionStore.access.organization.deletion_started_at === null,
);
const boolActionBlocked = computed(
  () => boolRefreshing.value || boolShowCancellation.value || sessionStore.busy,
);
const requestError = shallowRef<ApiError | null>(null);

const strTitle = computed(() => {
  if (sessionStore.access?.organization.deletion_started_at) return "Deletion in progress";
  if (sessionStore.access?.organization.deletion_requested_at) return "Deletion scheduled";
  if (sessionStore.access?.organization.suspended_at) return "Organization suspended";
  return "Organization access unavailable";
});

const strDescription = computed(() => {
  if (sessionStore.access?.organization.deletion_started_at)
    return "This organization's data is being deleted. Business operations are unavailable.";
  if (sessionStore.access?.organization.deletion_requested_at)
    return "Business operations are paused. Cleanup will permanently remove the organization, its current member accounts, and its Console data. An active organization administrator can cancel before cleanup starts.";
  if (sessionStore.access?.organization.suspended_at)
    return "This organization is suspended. Contact your service administrator for assistance.";
  return "Your account does not currently have access to an organization. Contact your service administrator.";
});

watch(boolCanCancel, (canCancel) => {
  if (!canCancel) boolShowCancellation.value = false;
});

async function refreshStatus(): Promise<void> {
  if (boolActionBlocked.value) return;
  requestError.value = null;
  boolRefreshing.value = true;
  try {
    await sessionStore.refreshSession();
  } finally {
    boolRefreshing.value = false;
  }
}

async function submitSignOut(): Promise<void> {
  if (boolActionBlocked.value) return;
  requestError.value = null;
  try {
    await sessionStore.signOutAccount();
  } catch (e) {
    requestError.value = getApiError(e);
  }
}
</script>

<style scoped></style>
