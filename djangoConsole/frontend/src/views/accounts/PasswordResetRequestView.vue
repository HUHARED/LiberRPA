<!-- FileName: PasswordResetRequestView.vue -->
<template>
  <AuthLayout>
    <v-btn
      :to="{ name: 'sign-in' }"
      variant="tonal"
      prepend-icon="mdi-arrow-left"
      class="mb-4"
      :disabled="boolSending">
      Back to Sign In
    </v-btn>

    <h1 class="text-h5 mb-2">Forgot Password</h1>

    <p class="text-medium-emphasis mb-6">
      Enter your account email address to request a password reset link.
    </p>

    <v-alert
      v-if="strEmailMessage"
      type="success"
      variant="tonal"
      class="mb-4"
      role="status">
      {{ strEmailMessage }}
    </v-alert>

    <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
      {{ requestError.message }}
      <p v-if="intRetrySeconds" class="mt-2">Try again in {{ intRetrySeconds }} seconds.</p>
    </v-alert>

    <v-form :novalidate="false" validate-on="submit" @submit.prevent="submitEmailRequest">
      <v-text-field
        v-model="strEmail"
        label="Email"
        name="email"
        type="email"
        autocomplete="email"
        variant="outlined"
        maxlength="254"
        spellcheck="false"
        autocapitalize="none"
        :rules="[validateRequiredEmail]"
        :error-messages="requestError?.fields.email ?? []"
        :disabled="boolSending"
        required />

      <v-btn
        type="submit"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-email-outline"
        block
        :loading="boolSending"
        :disabled="boolSending || intRetrySeconds > 0">
        Send Reset Link
      </v-btn>
    </v-form>
  </AuthLayout>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef, watch } from "vue";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "@/layouts/AuthLayout.vue";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { requestPasswordResetEmail } from "@/api/passwordReset";

const strEmail = ref("");
const strEmailMessage = ref("");
const boolSending = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
let boolUnmounted = false;

function validateRequiredEmail(value: string): true | string {
  return value.trim() ? true : "Enter your email address.";
}

async function submitEmailRequest(event: SubmitEventPromise): Promise<void> {
  if (boolSending.value || intRetrySeconds.value) return;
  const validation = await event;
  if (!validation.valid || boolUnmounted || boolSending.value || intRetrySeconds.value)
    return;
  boolSending.value = true;
  requestError.value = null;
  strEmailMessage.value = "";
  try {
    const response = await requestPasswordResetEmail(strEmail.value.trim());
    if (!boolUnmounted) strEmailMessage.value = response.message;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    boolSending.value = false;
  }
}

watch(strEmail, () => {
  strEmailMessage.value = "";
  if (!intRetrySeconds.value) requestError.value = null;
});

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
