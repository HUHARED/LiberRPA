<!-- FileName: InvitationDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    scrollable
    max-width="720"
    aria-labelledby="invitation-title"
    @update:model-value="!$event && closeDialog()">
    <v-card ref="feedbackContainer">
      <v-card-title id="invitation-title">
        {{
          action === "view"
            ? "Invitation Details"
            : action === "resend"
              ? "Resend Invitation"
              : "Revoke Invitation"
        }}
      </v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="boolLoading"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Loading invitation" />

        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
        </v-alert>

        <v-alert
          v-if="actionError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          The operation was not confirmed. {{ actionError.message }}
          <p
            v-for="strMessage in actionError.fields.department_roles"
            :key="strMessage"
            class="mt-2">
            {{ strMessage }}
          </p>

          <p v-if="intRetrySeconds" class="mt-2">
            Try again in {{ intRetrySeconds }} seconds.
          </p>
        </v-alert>

        <template v-if="invitationInfo">
          <dl class="detail-fields mb-4">
            <div>
              <dt class="text-caption text-medium-emphasis">Email</dt>
              <dd>{{ invitationInfo.email }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Status</dt>
              <dd class="text-capitalize">{{ strStatus }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Organization Role</dt>
              <dd>{{ invitationInfo.is_org_admin ? "OrgAdmin" : "Member" }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Email Delivery</dt>
              <dd>{{ getDeliveryLabel(invitationInfo.email_delivery) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Expires At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(invitationInfo.expires_at, strTimeZone, false) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Last Requested At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(invitationInfo.requested_at, strTimeZone, false) }}</dd>
            </div>

            <div class="full-width-field">
              <dt class="text-caption text-medium-emphasis">Department Roles</dt>

              <dd>
                <ul v-if="invitationInfo.department_roles.length" class="pl-4">
                  <li
                    v-for="assignment in invitationInfo.department_roles"
                    :key="assignment.department_id">
                    <RouterLink
                      v-if="!assignment.department_deleted"
                      :to="{
                        name: 'department-details',
                        params: { departmentId: assignment.department_id },
                      }"
                      target="_blank"
                      rel="noopener"
                      class="text-primary text-decoration-none">
                      {{ assignment.department_path }}
                    </RouterLink>
                    <span v-else>{{ assignment.department_path }} (Deleted)</span>
                    <span class="text-capitalize ms-1">— {{ assignment.role }}</span>
                  </li>
                </ul>

                <template v-else>
                  {{
                    invitationInfo.is_org_admin
                      ? "No explicit department roles; all departments are accessible."
                      : "No department access."
                  }}
                </template>
              </dd>
            </div>

            <div class="full-width-field">
              <dt class="text-caption text-medium-emphasis">Notes</dt>
              <dd class="text-pre-wrap">{{ invitationInfo.notes || "—" }}</dd>
            </div>
          </dl>

          <p class="mb-4">
            Email delivery status does not confirm that the recipient read the message.
            Revoke and create a new invitation to change roles or Notes.
          </p>

          <v-alert v-if="action === 'resend'" type="warning" variant="tonal" class="mb-4">
            Resending requests a new email and invalidates the previous invitation link. The
            assigned roles and Notes are kept.
          </v-alert>

          <v-alert
            v-else-if="action === 'revoke'"
            type="warning"
            variant="tonal"
            class="mb-4">
            Revoking invalidates this invitation link. It cannot remove an account that has
            already accepted the invitation.
          </v-alert>

          <p v-if="action === 'resend' && intResendSeconds > 0">
            Resend is available in {{ intResendSeconds }} seconds.
          </p>

          <p v-if="!boolOpen">This invitation is closed.</p>
        </template>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="closeDialog">
          {{ action === "view" ? "Close" : "Cancel" }}
        </v-btn>

        <v-btn
          v-if="requestError || actionError"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolLoading || boolSaving || !boolCanManage"
          @click="loadInvitation">
          {{ requestError ? "Retry" : "Check Status" }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="action !== 'view'"
          :color="action === 'revoke' ? 'error' : 'primary'"
          variant="tonal"
          :prepend-icon="action === 'resend' ? 'mdi-email-sync-outline' : 'mdi-cancel'"
          :loading="boolSaving"
          :disabled="boolActionBlocked"
          @click="submitAction">
          {{ action === "resend" ? "Resend" : "Revoke" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import {
  getInvitationDetails,
  updateInvitation,
  getInvitationStatus,
  getDeliveryLabel,
} from "@/api/invitations";
import type { InvitationResponse } from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{ invitationId: string; action: "view" | "resend" | "revoke" }>();
const emit = defineEmits<{ close: []; updated: [invitation: InvitationResponse] }>();
const sessionStore = useSessionStore();

const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);

const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const { intCurrentTimeMs, intRetrySeconds, setRetryDelay } = useRetryDelay();
const invitationInfo = shallowRef<InvitationResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const actionError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolSaving = ref(false);
let boolUnmounted = false;

const strStatus = computed(() =>
  invitationInfo.value
    ? getInvitationStatus(invitationInfo.value, intCurrentTimeMs.value)
    : "",
);

const boolOpen = computed(
  () => strStatus.value === "pending" || strStatus.value === "expired",
);

const intResendSeconds = computed(() =>
  invitationInfo.value
    ? Math.max(
        0,
        Math.ceil(
          (Date.parse(invitationInfo.value.resend_available_at) - intCurrentTimeMs.value) /
            1000,
        ),
      )
    : 0,
);

const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    boolSaving.value ||
    !boolCanManage.value ||
    !boolOpen.value ||
    intRetrySeconds.value > 0 ||
    (props.action === "resend" && intResendSeconds.value > 0) ||
    ["invitation_closed", "invitation_accepted"].includes(actionError.value?.code ?? ""),
);

async function loadInvitation(): Promise<void> {
  if (boolUnmounted || boolLoading.value || boolSaving.value || !boolCanManage.value)
    return;
  boolLoading.value = true;
  requestError.value = null;
  actionError.value = null;
  invitationInfo.value = null;
  try {
    const response = await getInvitationDetails(props.invitationId);
    if (!boolUnmounted) invitationInfo.value = response.invitation;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function submitAction(): Promise<void> {
  if (boolUnmounted || props.action === "view" || boolActionBlocked.value) return;
  boolSaving.value = true;
  actionError.value = null;
  try {
    const response = await updateInvitation(props.invitationId, props.action);
    if (!boolUnmounted) emit("updated", response.invitation);
  } catch (e) {
    if (boolUnmounted) return;
    actionError.value = getApiError(e);
    setRetryDelay(actionError.value.retryAfterSeconds);
    if (
      [0, 401, 403, 404].includes(actionError.value.statusCode) ||
      actionError.value.statusCode >= 500
    )
      invitationInfo.value = null;
    if (actionError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
    if (actionError.value && !boolUnmounted) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

onMounted(() => void loadInvitation());

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
