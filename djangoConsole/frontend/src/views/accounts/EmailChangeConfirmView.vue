<!-- FileName: EmailChangeConfirmView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-4">Confirm Email Change</h1>

    <v-alert
      v-if="boolConfirmed"
      type="success"
      variant="tonal"
      class="text-anywhere mb-4"
      role="status">
      Your email has been changed to
      <span class="font-weight-bold">{{ linkInfo?.new_email }}.</span>
      Use this address for future sign-ins. Your password, sessions and API keys remain
      active.
    </v-alert>

    <template v-else>
      <v-progress-linear
        v-if="boolLoading"
        indeterminate
        color="primary"
        class="mb-4"
        aria-label="Checking email change link" />

      <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
        {{ boolConfirmationFailed ? "Email change was not confirmed." : "" }}
        {{ requestError.message }}
        <p v-if="intRetrySeconds" class="mt-2">
          Try again in {{ intRetrySeconds }} seconds.
        </p>
      </v-alert>

      <template v-if="linkInfo">
        <v-text-field
          :model-value="linkInfo.new_email"
          label="New Email"
          variant="outlined"
          readonly />

        <p class="text-medium-emphasis mb-4">
          Expires at
          <span class="font-weight-bold">
            {{ formatDateTime(linkInfo.expires_at, "UTC") }}.
          </span>
        </p>

        <p class="mb-4">
          Select
          <span class="font-weight-bold">Confirm Email Change</span>
          to update the account that requested this link. Opening this page does not change
          the email or sign you in.
        </p>

        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-check"
          block
          class="mb-3"
          :loading="boolConfirming"
          :disabled="boolLoading || boolConfirming || intRetrySeconds > 0"
          @click="submitConfirmation">
          Confirm Email Change
        </v-btn>
      </template>

      <v-btn
        v-else-if="
          strToken && requestError && requestError.code !== 'invalid_email_change_token'
        "
        variant="tonal"
        prepend-icon="mdi-refresh"
        block
        class="mb-3"
        :disabled="boolLoading || boolConfirming || intRetrySeconds > 0"
        @click="loadLink">
        Retry
      </v-btn>
    </template>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-view-dashboard-outline"
      block
      :disabled="boolConfirming"
      :to="sessionStore.authenticated ? '/overview' : '/sign-in'">
      Open Console
    </v-btn>
  </AuthLayout>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AuthLayout from "@/layouts/AuthLayout.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { formatDateTime } from "@/app/formatters";

import { ApiError, getApiError } from "@/api/errors";
import { checkEmailChange, confirmEmailChange } from "@/api/profile";
import type { EmailChangeInfoResponse } from "@/api/generated/browserApi";

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const strToken = ref("");
const linkInfo = shallowRef<EmailChangeInfoResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolConfirming = ref(false);
const boolConfirmed = ref(false);
const boolConfirmationFailed = ref(false);
let intRequestRevision = 0;

async function loadLink(): Promise<void> {
  if (!strToken.value || boolLoading.value || boolConfirming.value || intRetrySeconds.value)
    return;
  const intCurrentRevision = intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await checkEmailChange(strToken.value);
    if (intCurrentRevision === intRequestRevision) linkInfo.value = response;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

async function submitConfirmation(): Promise<void> {
  if (
    !linkInfo.value ||
    boolLoading.value ||
    boolConfirming.value ||
    boolConfirmed.value ||
    intRetrySeconds.value
  )
    return;
  const intCurrentRevision = intRequestRevision;
  boolConfirming.value = true;
  requestError.value = null;
  boolConfirmationFailed.value = false;
  try {
    await confirmEmailChange(strToken.value);
    if (intCurrentRevision !== intRequestRevision) return;
    boolConfirmed.value = true;
    strToken.value = "";
    await router.replace({ name: "confirm-email-change", hash: "" });
    // The token belongs to its requesting account, which may differ from this browser's account.
    if (sessionStore.authenticated) await sessionStore.refreshSession();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    boolConfirmationFailed.value = true;
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (
      ["invalid_email_change_token", "email_already_registered"].includes(
        requestError.value.code,
      )
    )
      linkInfo.value = null;
  } finally {
    if (intCurrentRevision === intRequestRevision) boolConfirming.value = false;
  }
}

watch(
  () => route.hash,
  () => {
    if (boolConfirmed.value && !route.hash) return;
    intRequestRevision += 1;
    linkInfo.value = null;
    requestError.value = null;
    boolLoading.value = false;
    boolConfirming.value = false;
    boolConfirmed.value = false;
    boolConfirmationFailed.value = false;
    const parameters = new URLSearchParams(route.hash.slice(1));
    const strLinkToken = parameters.get("token") ?? "";
    strToken.value =
      parameters.getAll("token").length === 1 && /^[A-Za-z0-9_-]{43}$/.test(strLinkToken)
        ? strLinkToken
        : "";
    if (!strToken.value)
      requestError.value = new ApiError("The email change link is missing or invalid.", {
        code: "invalid_email_change_token",
      });
    else void loadLink();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
  strToken.value = "";
});
</script>

<style scoped></style>
