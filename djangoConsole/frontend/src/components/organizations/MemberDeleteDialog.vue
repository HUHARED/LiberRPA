<!-- FileName: MemberDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolDeleting"
    scrollable
    max-width="640"
    aria-labelledby="member-delete-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="member-delete-title">Delete Account</v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="boolLoading"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Checking account deletion conditions" />

        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
        </v-alert>

        <v-alert v-if="deleteError" type="error" variant="tonal" class="mb-4" role="alert">
          Deletion was not confirmed. {{ deleteError.message }}
          <p v-if="!deletionInfo" class="mt-2">
            Check the current account before trying again.
          </p>

          <p v-if="intRetrySeconds" class="mt-2">
            Try again in {{ intRetrySeconds }} seconds.
          </p>
        </v-alert>

        <v-alert v-if="boolOwnDeletionBlocked" type="warning" variant="tonal" role="alert">
          The organization must retain at least one active administrator. Assign another
          administrator before deleting your account.
        </v-alert>

        <v-form
          v-if="!boolOwnDeletionBlocked"
          id="member-delete-form"
          validate-on="submit"
          @submit.prevent="submitDelete">
          <v-text-field
            :model-value="`${deletionInfo?.user.username ?? user.username} (${deletionInfo?.user.email ?? user.email})`"
            label="Account to delete"
            variant="plain"
            readonly />

          <v-alert
            v-if="deletionInfo && !deletionInfo.can_delete"
            type="warning"
            variant="tonal"
            class="mb-4">
            The organization must retain at least one active administrator.
          </v-alert>

          <p class="mb-4">
            This permanently deletes the account, its department roles, API Keys and client
            associations. Organization resources and history remain. Creating an account
            with the same email later will not restore this account.
          </p>

          <PasswordField
            v-model="strPassword"
            :label="boolOwnAccount ? 'Current Password' : 'Your Current Password'"
            autocomplete="current-password"
            :rules="[validatePassword]"
            :error-messages="deleteError?.fields.current_password ?? []"
            :disabled="boolLoading || boolDeleting || !deletionInfo?.can_delete"
            :hint="
              boolOwnAccount
                ? undefined
                : 'Enter your own password, not the member’s password.'
            "
            :persistent-hint="!boolOwnAccount"
            required />
        </v-form>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolDeleting"
          @click="closeDialog">
          {{ boolOwnDeletionBlocked ? "Close" : "Cancel" }}
        </v-btn>

        <v-btn
          v-if="
            !boolOwnDeletionBlocked &&
            (requestError ||
              (deleteError && !deletionInfo) ||
              (deletionInfo && !deletionInfo.can_delete))
          "
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolLoading || boolDeleting || !boolCanDelete"
          @click="loadPreview">
          {{ requestError ? "Retry" : "Check Again" }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="!boolOwnDeletionBlocked"
          type="submit"
          form="member-delete-form"
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="boolDeleting"
          :disabled="
            boolLoading ||
            boolDeleting ||
            !boolCanDelete ||
            !deletionInfo?.can_delete ||
            intRetrySeconds > 0
          ">
          Delete Account
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { getAccountDeletionPreview, deleteAccount } from "@/api/accountDeletion";
import type {
  AccountDeletionPreviewResponse,
  UserResponse,
} from "@/api/generated/browserApi";

const props = defineProps<{ user: UserResponse }>();
const emit = defineEmits<{ close: []; deleted: [user: UserResponse] }>();
const sessionStore = useSessionStore();
const boolOwnAccount = props.user.id === sessionStore.session?.user.id;

const boolCanDelete = computed(
  () =>
    sessionStore.access?.business_available &&
    (boolOwnAccount || sessionStore.access.is_org_admin),
);

const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const deletionInfo = shallowRef<AccountDeletionPreviewResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const deleteError = shallowRef<ApiError | null>(null);
const strPassword = ref("");
const boolLoading = ref(false);
const boolDeleting = ref(false);

const boolOwnDeletionBlocked = computed(
  () => boolOwnAccount && deletionInfo.value?.can_delete === false,
);

let boolUnmounted = false;

async function loadPreview(): Promise<void> {
  if (boolUnmounted || boolLoading.value || boolDeleting.value || !boolCanDelete.value)
    return;
  boolLoading.value = true;
  deletionInfo.value = null;
  requestError.value = null;
  deleteError.value = null;
  strPassword.value = "";
  try {
    const response = await getAccountDeletionPreview(
      boolOwnAccount ? undefined : props.user.id,
    );
    if (!boolUnmounted) deletionInfo.value = response;
  } catch (e) {
    if (boolUnmounted) return;

    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function validatePassword(value: string): true | string {
  return value ? true : "Enter your current password.";
}

function closeDialog(): void {
  if (!boolDeleting.value) emit("close");
}

async function submitDelete(event: SubmitEventPromise): Promise<void> {
  if (
    boolUnmounted ||
    boolLoading.value ||
    boolDeleting.value ||
    !boolCanDelete.value ||
    !deletionInfo.value?.can_delete ||
    intRetrySeconds.value
  )
    return;

  const validation = await event;
  if (
    !validation.valid ||
    boolUnmounted ||
    boolLoading.value ||
    boolDeleting.value ||
    !boolCanDelete.value ||
    !deletionInfo.value?.can_delete ||
    intRetrySeconds.value > 0
  )
    return;

  boolDeleting.value = true;
  deleteError.value = null;
  try {
    await deleteAccount(strPassword.value, boolOwnAccount ? undefined : props.user.id);
    if (boolOwnAccount) sessionStore.finishAccountSignOut("account_deleted");
    else if (!boolUnmounted) emit("deleted", deletionInfo.value?.user ?? props.user);
  } catch (e) {
    if (boolUnmounted) return;
    deleteError.value = getApiError(e);
    setRetryDelay(deleteError.value.retryAfterSeconds);
    if (deleteError.value.code === "last_org_admin" && deletionInfo.value) {
      deletionInfo.value = {
        ...deletionInfo.value,
        can_delete: false,
        blockers: [{ code: "last_org_admin" }],
      };
    } else if (
      !deleteError.value.fields.current_password &&
      deleteError.value.statusCode !== 429
    ) {
      deletionInfo.value = null;
    }
    if (deleteError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolDeleting.value = false;
    strPassword.value = "";
  }
}

onMounted(() => void loadPreview());

onBeforeUnmount(() => {
  boolUnmounted = true;
  strPassword.value = "";
});
</script>

<style scoped></style>
