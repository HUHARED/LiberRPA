<!-- FileName: AccountActionDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSubmitting"
    scrollable
    max-width="640"
    aria-labelledby="account-action-title"
    @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title id="account-action-title">{{ strTitle }}</v-card-title>

      <v-card-text>
        <v-alert
          v-if="boolEmailQueued"
          type="success"
          variant="tonal"
          class="text-anywhere"
          role="status">
          Verification email queued for
          <span class="font-weight-bold">{{ strNewEmail }}.</span>
          Open the link in that mailbox and select
          <span class="font-weight-bold">Confirm Email Change.</span>
          Your current email remains unchanged until then.
        </v-alert>

        <template v-else>
          <p v-if="action === 'password'" class="mb-4">
            Changing your password will sign you out of all sessions and revoke your active
            API keys.
          </p>

          <p v-else-if="action === 'sessions'" class="mb-4">
            This signs out other browsers and connected clients, and clears their Executor
            associations. This browser session, tabs sharing it, and API keys remain active.
            Executor records are kept.
          </p>

          <p v-else class="mb-4">
            Confirm the new address through its verification email. Your password, sessions
            and API keys remain active. The link expires after
            <span class="font-weight-bold">one hour;</span>
            wait at least
            <span class="font-weight-bold">five minutes</span>
            before requesting another email.
          </p>

          <v-alert
            v-if="requestError"
            type="error"
            variant="tonal"
            class="mb-4"
            role="alert">
            {{ requestError.message }}
            <p v-if="intRetrySeconds" class="mt-2">
              Try again in {{ intRetrySeconds }} seconds.
            </p>
          </v-alert>

          <v-form
            id="account-action-form"
            :novalidate="false"
            validate-on="submit"
            @submit.prevent="submitAction">
            <v-text-field
              v-if="action === 'email'"
              :model-value="sessionStore.session?.user.email"
              label="Current Email"
              variant="outlined"
              readonly />

            <PasswordField
              v-model="strCurrentPassword"
              label="Current Password"
              autocomplete="current-password"
              :rules="[validateRequiredPassword]"
              :error-messages="requestError?.fields.current_password ?? []"
              :disabled="boolSubmitting"
              required />

            <template v-if="action === 'password'">
              <PasswordField
                v-model="strNewPassword"
                label="New Password"
                autocomplete="new-password"
                hint="Use 15–128 characters."
                persistent-hint
                :rules="[validateRequiredPassword]"
                :error-messages="requestError?.fields.new_password ?? []"
                :disabled="boolSubmitting"
                required />

              <PasswordField
                v-model="strConfirmPassword"
                label="Confirm New Password"
                autocomplete="new-password"
                :rules="[validateRequiredPassword, validatePasswordMatch]"
                :error-messages="requestError?.fields.confirm_password ?? []"
                :disabled="boolSubmitting"
                required />
            </template>

            <v-text-field
              v-if="action === 'email'"
              v-model="strNewEmail"
              label="New Email"
              type="email"
              autocomplete="email"
              variant="outlined"
              :maxlength="254"
              :rules="[validateEmail]"
              :error-messages="requestError?.fields.new_email ?? []"
              :disabled="boolSubmitting"
              spellcheck="false"
              autocapitalize="none"
              required />
          </v-form>
        </template>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSubmitting"
          @click="emit('close')">
          {{ boolEmailQueued ? "Done" : "Cancel" }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="!boolEmailQueued"
          type="submit"
          form="account-action-form"
          color="primary"
          variant="tonal"
          :prepend-icon="
            action === 'email'
              ? 'mdi-email-outline'
              : action === 'password'
                ? 'mdi-lock-reset'
                : 'mdi-logout'
          "
          :loading="boolSubmitting"
          :disabled="boolSubmitting || sessionStore.busy || intRetrySeconds > 0">
          {{ action === "email" ? "Send Verification Email" : strTitle }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { changePassword, signOutOtherSessions, requestEmailChange } from "@/api/profile";

const props = defineProps<{ action: "password" | "sessions" | "email" }>();
const emit = defineEmits<{ close: []; completed: [message: string] }>();
const sessionStore = useSessionStore();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();

const strTitle = computed(() => {
  if (props.action === "password") return "Change Password";
  if (props.action === "sessions") return "Sign Out Other Sessions";
  return "Change Email";
});

const strCurrentPassword = ref("");
const strNewPassword = ref("");
const strConfirmPassword = ref("");
const strNewEmail = ref("");
const requestError = shallowRef<ApiError | null>(null);
const boolSubmitting = ref(false);
const boolEmailQueued = ref(false);
let boolUnmounted = false;

function validateRequiredPassword(value: string): true | string {
  return value ? true : "Enter a password.";
}

function validatePasswordMatch(value: string): true | string {
  return value === strNewPassword.value ? true : "The new passwords do not match.";
}

function validateEmail(value: string): true | string {
  return value.trim() ? true : "Enter the new email address.";
}

function clearPasswords(): void {
  strCurrentPassword.value = "";
  strNewPassword.value = "";
  strConfirmPassword.value = "";
}

async function submitAction(event: SubmitEventPromise): Promise<void> {
  if (boolSubmitting.value || sessionStore.busy || intRetrySeconds.value) return;
  const validation = await event;
  if (
    !validation.valid ||
    boolUnmounted ||
    boolSubmitting.value ||
    sessionStore.busy ||
    intRetrySeconds.value
  )
    return;
  boolSubmitting.value = true;
  sessionStore.busy = true;
  requestError.value = null;
  try {
    if (props.action === "password") {
      await changePassword({
        current_password: strCurrentPassword.value,
        new_password: strNewPassword.value,
        confirm_password: strConfirmPassword.value,
      });
      sessionStore.finishAccountSignOut("password_changed");
    } else if (props.action === "sessions") {
      await signOutOtherSessions({ current_password: strCurrentPassword.value });
      if (!boolUnmounted)
        emit(
          "completed",
          "Other sessions signed out. This session and your API keys remain active.",
        );
    } else {
      await requestEmailChange({
        current_password: strCurrentPassword.value,
        new_email: strNewEmail.value,
      });
      if (!boolUnmounted) boolEmailQueued.value = true;
    }
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    clearPasswords();
    boolSubmitting.value = false;
    sessionStore.busy = false;
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
  clearPasswords();
});
</script>

<style scoped></style>
