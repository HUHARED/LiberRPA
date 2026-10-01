<!-- FileName: MemberInvitations.vue -->
<template>
  <v-row align="center" class="mt-6 mb-4">
    <v-col>
      <h3 class="text-h5 mb-2">Invitations</h3>
      <p class="text-medium-emphasis">
        Pending and expired invitations. Accepted and revoked invitations leave this list.
      </p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-account-plus-outline"
        :disabled="boolActionBlocked"
        @click="openInvitationForm">
        Invite Member
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
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="invitationPage" class="mt-2">
      Previously loaded invitations are shown and may be out of date.
    </p>
    <template #append>
      <v-btn
        variant="tonal"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadInvitations()">
        Retry
      </v-btn>
    </template>
  </v-alert>
  <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
    Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
  </p>
  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="arrHeader"
      :items="invitationPage?.invitations ?? []"
      :items-length="invitationPage?.pagination.total_count ?? 0"
      :items-per-page="invitationPage?.pagination.page_size ?? 50"
      :page="invitationPage?.pagination.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      loading-text="Loading invitations…"
      disable-sort
      hide-default-footer>
      <template #item.email="{ item }">
        <span class="table-text">{{ item.email }}</span>
      </template>
      <template #item.status="{ item }">
        <span class="text-capitalize">
          {{ getInvitationStatus(item, intCurrentTimeMs) }}
        </span>
      </template>
      <template #item.roles="{ item }">
        <template v-if="item.is_org_admin">
          <v-chip color="primary" size="small" variant="tonal">OrgAdmin </v-chip>
          <p class="text-body-2 mt-1">All departments</p>
        </template>
        <ul v-else-if="item.department_roles.length" class="list-unstyled">
          <li
            v-for="assignment in item.department_roles"
            :key="assignment.department_id"
            class="table-text py-1">
            {{ assignment.department_path
            }}{{ assignment.department_deleted ? " (Deleted)" : ""
            }}<span class="text-capitalize"> — {{ assignment.role }}</span>
          </li>
        </ul>
        <span v-else class="text-medium-emphasis">No department access</span>
      </template>
      <template #item.expires_at="{ item }">
        {{ formatDateTime(item.expires_at, strTimeZone) }}
      </template>
      <template #item.email_delivery="{ item }">
        {{ getDeliveryLabel(item.email_delivery) }}
      </template>
      <template #item.actions="{ item }">
        <v-btn
          variant="text"
          size="small"
          :disabled="boolActionBlocked"
          :aria-label="`View invitation for ${item.email}`"
          @click="openInvitation(item.id, 'view')">
          View
        </v-btn>
        <v-btn
          variant="text"
          size="small"
          :disabled="boolActionBlocked"
          :aria-label="`Resend invitation to ${item.email}`"
          @click="openInvitation(item.id, 'resend')">
          Resend
        </v-btn>
        <v-btn
          color="error"
          variant="text"
          size="small"
          :disabled="boolActionBlocked"
          :aria-label="`Revoke invitation for ${item.email}`"
          @click="openInvitation(item.id, 'revoke')">
          Revoke
        </v-btn>
      </template>
      <template #no-data>{{
        requestError
          ? "The invitation list could not be loaded."
          : "No pending or expired invitations."
      }}</template>
    </v-data-table-server>
    <template v-if="invitationPage">
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ invitationPage.pagination.total_count }} invitations · Page
          {{ invitationPage.pagination.page }} of
          {{ invitationPage.pagination.total_pages }}
        </p>
        <v-pagination
          v-if="invitationPage.pagination.total_pages > 1"
          :model-value="invitationPage.pagination.page"
          :length="invitationPage.pagination.total_pages"
          :total-visible="5"
          :disabled="boolActionBlocked"
          aria-label="Invitation pages"
          @update:model-value="loadInvitations" />
      </div>
    </template>
  </v-card>
  <MembershipFormDialog
    v-if="boolNewInvitation"
    @close="boolNewInvitation = false"
    @invited="handleInvited" />
  <InvitationDialog
    v-if="selectedInvitation"
    :invitation-id="selectedInvitation.id"
    :action="selectedInvitation.action"
    @close="selectedInvitation = null"
    @updated="handleInvitationUpdated" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

import MembershipFormDialog from "./MembershipFormDialog.vue";
import InvitationDialog from "./InvitationDialog.vue";

import { useSessionStore } from "../stores/sessionStore";
import { useRetryDelay } from "../composables/useRetryDelay";

import { type ApiError, getApiError } from "../api/errors";
import {
  getInvitationList,
  getInvitationStatus,
  getDeliveryLabel,
} from "../api/invitations";
import type {
  InvitationResponse,
  InvitationListResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const { intCurrentTimeMs } = useRetryDelay();
const arrHeader = computed(() => [
  { title: "Email", key: "email", minWidth: 220 },
  { title: "Status", key: "status", minWidth: 100 },
  { title: "Roles / Departments", key: "roles", minWidth: 220 },
  { title: `Expires At (${strTimeZone.value})`, key: "expires_at", minWidth: 240 },
  { title: "Email Delivery", key: "email_delivery", minWidth: 150 },
  { title: "Actions", key: "actions", width: 260 },
]);
const invitationPage = shallowRef<InvitationListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolNewInvitation = ref(false);
const selectedInvitation = shallowRef<{
  id: string;
  action: "view" | "resend" | "revoke";
} | null>(null);
const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    boolNewInvitation.value ||
    selectedInvitation.value !== null ||
    !sessionStore.access?.is_org_admin ||
    !sessionStore.access.business_available,
);
const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;
let intRequestedPage = 1;

async function loadInvitations(pageNumber: number = intRequestedPage): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getInvitationList(pageNumber);
    if (intCurrentRevision !== intRequestRevision) return;
    invitationPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    if (requestError.value.code === "invitation_not_found" && pageNumber > 1) {
      await loadInvitations(1);
      return;
    }
    if ([401, 403].includes(requestError.value.statusCode)) {
      invitationPage.value = null;
      strUpdatedAt.value = null;
      boolNewInvitation.value = false;
      selectedInvitation.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openInvitationForm(): void {
  if (boolActionBlocked.value) return;
  strSuccessMessage.value = "";
  boolNewInvitation.value = true;
}

function openInvitation(id: string, action: "view" | "resend" | "revoke"): void {
  if (boolActionBlocked.value) return;
  strSuccessMessage.value = "";
  selectedInvitation.value = { id, action };
}

function handleInvited(invitation: InvitationResponse): void {
  boolNewInvitation.value = false;
  strSuccessMessage.value = `Invitation created for ${invitation.email}. Check Email Delivery for its delivery status.`;
  void loadInvitations(1);
}

function handleInvitationUpdated(invitation: InvitationResponse): void {
  const action = selectedInvitation.value?.action;
  selectedInvitation.value = null;
  strSuccessMessage.value =
    action === "revoke"
      ? `Invitation for ${invitation.email} revoked.`
      : `Resend requested for ${invitation.email}. The previous invitation link is no longer valid.`;
  // Apply the confirmed result before refreshing so a failed read cannot restore an obsolete action target.
  if (invitationPage.value) {
    const arrInvitation = invitationPage.value.invitations
      .map((entry) => (entry.id === invitation.id ? invitation : entry))
      .filter((entry) => entry.status !== "accepted" && entry.status !== "revoked");
    const intRemoved = invitationPage.value.invitations.length - arrInvitation.length;
    invitationPage.value = {
      ...invitationPage.value,
      invitations: arrInvitation,
      pagination: {
        ...invitationPage.value.pagination,
        total_count: invitationPage.value.pagination.total_count - intRemoved,
      },
    };
  }
  strUpdatedAt.value = null;
  void loadInvitations();
}

onMounted(() => void loadInvitations());
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
