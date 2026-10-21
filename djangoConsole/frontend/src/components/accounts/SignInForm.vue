<!-- FileName: SignInForm.vue -->
<template>
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

  <v-alert
    v-else-if="!platform && sessionStore.notice === 'account_created'"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    Account created. Sign in with your invited email address and password.
  </v-alert>

  <v-alert
    v-else-if="!platform && sessionStore.notice === 'organization_created'"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    Organization created. Sign in with your verified email address and password.
  </v-alert>

  <v-alert
    v-else-if="!platform && sessionStore.notice === 'password_changed'"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    Password changed. All previous sessions and active API keys were revoked. Sign in with
    your new password.
  </v-alert>

  <v-alert
    v-else-if="!platform && sessionStore.notice === 'account_deleted'"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    Your account has been deleted.
  </v-alert>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <span v-if="intRetrySeconds > 0" class="d-block mt-1">
      Try again in {{ intRetrySeconds }} seconds.
    </span>
  </v-alert>

  <v-form :novalidate="false" validate-on="submit" @submit.prevent="submitSignIn">
    <v-text-field
      v-if="platform"
      id="platform-sign-in-login"
      :model-value="STR_PLATFORM_ADMIN_LOGIN"
      name="platform_login"
      label="Login Name"
      type="text"
      autocomplete="username"
      variant="plain"
      density="compact"
      class="mb-3"
      spellcheck="false"
      autocapitalize="none"
      readonly />

    <v-text-field
      v-else
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
      append-icon="mdi-arrow-right"
      block
      class="mt-4"
      :loading="sessionStore.busy"
      :disabled="intRetrySeconds > 0">
      Sign In
    </v-btn>
  </v-form>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { getSafeReturnPath } from "@/app/navigation";

import { ApiError, getApiError } from "@/api/errors";

const STR_PLATFORM_ADMIN_LOGIN = "admin";

const props = withDefaults(defineProps<{ platform?: boolean }>(), { platform: false });

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const strEmail = ref("");
const strPassword = ref("");
const boolRememberMe = ref(false);
const boolPasswordVisible = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const { intRetrySeconds, setRetryDelay } = useRetryDelay();

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
      props.platform
        ? {
            platform_login: STR_PLATFORM_ADMIN_LOGIN,
            password: strPassword.value,
            remember_me: boolRememberMe.value,
          }
        : {
            email: strEmail.value.trim(),
            password: strPassword.value,
            remember_me: boolRememberMe.value,
          },
    );
    if (sessionStore.authenticated) {
      strPassword.value = "";
      await router.replace(
        getSafeReturnPath(
          route.query.returnTo,
          sessionStore.session?.user.is_platform_admin,
        ),
      );
    } else if (!sessionStore.unavailable && sessionStore.status === "anonymous") {
      requestError.value = new ApiError(
        "The session could not be kept. Allow cookies for this site and try again.",
      );
    }
  } catch (e) {
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  }
}

onBeforeUnmount(() => {
  strPassword.value = "";
});
</script>

<style scoped></style>
