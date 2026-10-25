<!-- FileName: PasswordResetView.vue -->
<template>
  <AuthLayout ref="feedbackContainer">
    <v-btn
      v-if="!boolCompleted"
      :to="sessionStore.authenticated ? '/overview' : '/sign-in'"
      variant="tonal"
      :prepend-icon="
        sessionStore.authenticated ? 'mdi-view-dashboard-outline' : 'mdi-arrow-left'
      "
      class="mb-4"
      :disabled="boolSaving">
      {{ sessionStore.authenticated ? "Open Console" : "Back to Sign In" }}
    </v-btn>

    <h1 class="text-h5 mb-4">Reset Password</h1>

    <template v-if="boolCompleted">
      <v-alert type="success" variant="tonal" class="text-anywhere mb-4" role="status">
        The password for
        <span class="font-weight-bold">{{ linkInfo?.email }}</span>
        has been reset.
      </v-alert>

      <p v-if="sessionStore.authenticated" class="text-anywhere mb-4">
        You are still signed in as
        <span class="text-highlight font-weight-bold">
          {{ sessionStore.session?.user.email }}.
        </span>
      </p>

      <v-btn
        :to="sessionStore.authenticated ? '/overview' : '/sign-in'"
        color="primary"
        variant="tonal"
        :prepend-icon="
          sessionStore.authenticated ? 'mdi-view-dashboard-outline' : undefined
        "
        :append-icon="sessionStore.authenticated ? undefined : 'mdi-arrow-right'"
        block>
        {{ sessionStore.authenticated ? "Open Console" : "Sign In" }}
      </v-btn>
    </template>

    <template v-else>
      <v-progress-linear
        v-if="boolChecking"
        indeterminate
        color="primary"
        class="mb-4"
        aria-label="Checking password reset link" />

      <v-alert
        v-if="requestError"
        ref="errorAlert"
        tabindex="-1"
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
        v-if="linkInfo"
        :novalidate="false"
        validate-on="submit"
        @submit.prevent="submitPasswordReset">
        <v-text-field
          :model-value="linkInfo.email"
          label="Email"
          autocomplete="username"
          variant="plain"
          readonly />

        <PasswordField
          v-model="strNewPassword"
          label="New Password"
          autocomplete="new-password"
          class="mb-3"
          :rules="[validateRequiredPassword]"
          :error-messages="requestError?.fields.new_password ?? []"
          :disabled="boolSaving"
          required />

        <PasswordField
          v-model="strConfirmPassword"
          label="Confirm Password"
          autocomplete="new-password"
          class="mb-3"
          :rules="[validateRequiredPassword, validatePasswordMatch]"
          :error-messages="requestError?.fields.confirm_password ?? []"
          :disabled="boolSaving"
          required />

        <p class="mb-4">
          Resetting your password will sign you out of all sessions and revoke your active
          API keys.
        </p>

        <v-btn
          type="submit"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-lock-reset"
          block
          :loading="boolSaving"
          :disabled="!boolCanReset">
          Reset Password
        </v-btn>
      </v-form>

      <template v-else-if="!boolChecking">
        <v-btn
          v-if="strToken && requestError?.code !== 'invalid_password_reset_token'"
          variant="tonal"
          prepend-icon="mdi-refresh"
          block
          class="mb-3"
          :disabled="intRetrySeconds > 0"
          @click="loadLink">
          Check Again
        </v-btn>

        <v-btn
          :to="{ name: 'forgot-password' }"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-email-sync-outline"
          block>
          Request a New Reset Link
        </v-btn>
      </template>
    </template>
  </AuthLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "@/layouts/AuthLayout.vue";
import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { ApiError, getApiError } from "@/api/errors";
import { checkPasswordReset, completePasswordReset } from "@/api/passwordReset";
import type { PasswordResetInfoResponse } from "@/api/passwordReset";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const strToken = ref("");
const linkInfo = shallowRef<PasswordResetInfoResponse | null>(null);
const strNewPassword = ref("");
const strConfirmPassword = ref("");
const requestError = shallowRef<ApiError | null>(null);
const boolChecking = ref(false);
const boolSaving = ref(false);
const boolCompleted = ref(false);
const boolCanReset = computed(
  () =>
    !boolChecking.value &&
    !boolSaving.value &&
    !boolCompleted.value &&
    !sessionStore.busy &&
    !intRetrySeconds.value &&
    !!linkInfo.value &&
    !!strNewPassword.value &&
    !!strConfirmPassword.value,
);
let intRequestRevision = 0;

function validateRequiredPassword(value: string): true | string {
  return value ? true : "Enter a password.";
}

function validatePasswordMatch(value: string): true | string {
  return value === strNewPassword.value ? true : "The new passwords do not match.";
}

function clearPasswords(): void {
  strNewPassword.value = "";
  strConfirmPassword.value = "";
}

async function loadLink(): Promise<void> {
  if (!strToken.value || boolChecking.value || boolSaving.value || intRetrySeconds.value)
    return;
  const intCurrentRevision = intRequestRevision;
  boolChecking.value = true;
  requestError.value = null;
  try {
    const response = await checkPasswordReset(strToken.value);
    if (intCurrentRevision === intRequestRevision) linkInfo.value = response;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (intCurrentRevision === intRequestRevision) boolChecking.value = false;
  }
}

async function submitPasswordReset(event: SubmitEventPromise): Promise<void> {
  if (!boolCanReset.value) return;
  const intCurrentRevision = intRequestRevision;
  const validation = await event;
  if (intCurrentRevision !== intRequestRevision || !boolCanReset.value || !linkInfo.value)
    return;
  if (!validation.valid) {
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el, undefined, true);
    return;
  }
  const strResetEmail = linkInfo.value.email;
  boolSaving.value = true;
  sessionStore.busy = true;
  requestError.value = null;
  try {
    await completePasswordReset({
      token: strToken.value,
      new_password: strNewPassword.value,
      confirm_password: strConfirmPassword.value,
    });
    if (intCurrentRevision !== intRequestRevision) return;
    boolCompleted.value = true;
    strToken.value = "";
    clearPasswords();
    // A reset link must not sign out a different account already open in this browser.
    if (!sessionStore.authenticated || sessionStore.session?.user.email === strResetEmail) {
      sessionStore.finishAccountSignOut("password_changed");
      await router.replace({ name: "sign-in" });
    } else {
      await router.replace({ name: "reset-password", hash: "" });
    }
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (requestError.value.code === "invalid_password_reset_token") {
      linkInfo.value = null;
      clearPasswords();
    }
  } finally {
    sessionStore.busy = false;
    if (intCurrentRevision === intRequestRevision) {
      boolSaving.value = false;
      if (requestError.value) {
        await nextTick();
        revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el, true);
      }
    }
  }
}

watch(
  () => route.hash,
  () => {
    if (boolCompleted.value && !route.hash) return;
    intRequestRevision += 1;
    linkInfo.value = null;
    requestError.value = null;
    boolChecking.value = false;
    boolSaving.value = false;
    boolCompleted.value = false;
    clearPasswords();
    const parameters = new URLSearchParams(route.hash.slice(1));
    const strLinkToken = parameters.get("token") ?? "";
    strToken.value =
      parameters.getAll("token").length === 1 && /^[A-Za-z0-9_-]{43}$/.test(strLinkToken)
        ? strLinkToken
        : "";
    if (!strToken.value)
      requestError.value = new ApiError("The password reset link is missing or invalid.", {
        code: "invalid_password_reset_token",
      });
    else void loadLink();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
  strToken.value = "";
  clearPasswords();
});
</script>

<style scoped></style>
