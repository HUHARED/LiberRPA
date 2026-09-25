<!-- FileName: SignInView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-2">Sign in to Console</h1>
    <p class="text-body-2 text-medium-emphasis mb-6">
      Enter your account details to open your workspace.
    </p>
    <v-alert
      v-if="sessionStore.notice === 'expired'"
      type="info"
      variant="tonal"
      class="mb-4"
      role="status">
      Your session has ended. Sign in again to continue.
    </v-alert>
    <v-alert
      v-else-if="sessionStore.notice === 'signed_out'"
      type="success"
      variant="tonal"
      class="mb-4"
      role="status">
      You have signed out.
    </v-alert>
    <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
      {{ requestError.message }}
      <span v-if="intRetrySeconds > 0" class="d-block mt-1">
        Try again in {{ intRetrySeconds }} seconds.
      </span>
    </v-alert>
    <v-form :novalidate="false" validate-on="submit" @submit.prevent="submitSignIn">
      <v-text-field
        id="sign-in-email"
        v-model="strEmail"
        name="email"
        label="Email"
        type="email"
        autocomplete="username"
        placeholder="you@example.com"
        variant="underlined"
        density="compact"
        class="mb-3"
        :maxlength="254"
        :rules="[validateRequiredEmail]"
        :disabled="sessionStore.busy"
        spellcheck="false"
        autocapitalize="none"
        required />
      <v-text-field
        id="sign-in-password"
        v-model="strPassword"
        name="password"
        label="Password"
        autocomplete="current-password"
        variant="underlined"
        density="compact"
        class="mb-2"
        :type="boolPasswordVisible ? 'text' : 'password'"
        :rules="[validateRequiredPassword]"
        :disabled="sessionStore.busy"
        required>
        <template #append-inner>
          <v-btn
            :icon="boolPasswordVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
            variant="text"
            size="small"
            :aria-label="boolPasswordVisible ? 'Hide password' : 'Show password'"
            :aria-pressed="boolPasswordVisible"
            :disabled="sessionStore.busy"
            type="button"
            @click="boolPasswordVisible = !boolPasswordVisible" />
        </template>
      </v-text-field>
      <v-checkbox
        v-model="boolRememberMe"
        color="primary"
        label="Remember me for 14 days"
        hide-details
        density="compact"
        :disabled="sessionStore.busy" />
      <v-btn
        type="submit"
        color="primary"
        variant="tonal"
        block
        class="mt-4"
        :loading="sessionStore.busy"
        :disabled="intRetrySeconds > 0"
        append-icon="mdi-arrow-right">
        Sign In
      </v-btn>
    </v-form>
    <v-divider class="my-4" />
    <p class="text-body-2 text-medium-emphasis">
      Use the email address associated with your organization.
    </p>
  </AuthLayout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "../layouts/AuthLayout.vue";

import { useSessionStore } from "../stores/sessionStore";

import { getSafeReturnPath } from "../app/navigation";
import { ApiError, getApiError } from "../api/errors";

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const strEmail = ref("");
const strPassword = ref("");
const boolRememberMe = ref(false);
const boolPasswordVisible = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const intRetryUntilMs = ref(0);
const intCurrentTimeMs = ref(Date.now());
const intRetrySeconds = computed(() =>
  Math.max(0, Math.ceil((intRetryUntilMs.value - intCurrentTimeMs.value) / 1000)),
);
const intervalHandle = setInterval(() => {
  intCurrentTimeMs.value = Date.now();
}, 1000);
onBeforeUnmount(() => {
  clearInterval(intervalHandle);
  strPassword.value = "";
});

function validateRequiredEmail(value: string): true | string {
  return value.trim() ? true : "Enter your email address.";
}

function validateRequiredPassword(value: string): true | string {
  return value ? true : "Enter your password.";
}

async function submitSignIn(event: SubmitEventPromise): Promise<void> {
  if (sessionStore.busy || intRetrySeconds.value > 0) return;
  const validationResult = await event;
  if (!validationResult.valid || sessionStore.busy || intRetrySeconds.value > 0) return;
  requestError.value = null;
  try {
    await sessionStore.signInAccount(
      strEmail.value.trim(),
      strPassword.value,
      boolRememberMe.value,
    );
    if (sessionStore.authenticated) {
      strPassword.value = "";
      await router.replace(getSafeReturnPath(route.query.returnTo));
    } else if (!sessionStore.unavailable && sessionStore.status === "anonymous") {
      requestError.value = new ApiError(
        "The session could not be kept. Allow cookies for this site and try again.",
      );
    }
  } catch (e) {
    requestError.value = getApiError(e);
    const intWaitSeconds = requestError.value.retryAfterSeconds;
    if (intWaitSeconds !== null) {
      intCurrentTimeMs.value = Date.now();
      intRetryUntilMs.value = intCurrentTimeMs.value + intWaitSeconds * 1000;
    }
  }
}
</script>

<style scoped></style>
