<!-- FileName: CreateOrganizationView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-2">Create Organization</h1>
    <p class="text-medium-emphasis mb-6">
      Verify your email, then create your organization and administrator account.
    </p>
    <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
      {{ requestError.message }}
      <p v-for="message in requestError.fields.__all__" :key="message" class="mt-2">
        {{ message }}
      </p>
      <p v-if="intRetrySeconds" class="mt-2">Try again in {{ intRetrySeconds }} seconds.</p>
    </v-alert>
    <template v-if="isCreated">
      <v-alert type="success" variant="tonal" class="mb-4" role="status">
        Organization created. Sign in with your verified email address and password.
      </v-alert>
      <v-btn :to="{ name: 'sign-in' }" color="primary" variant="tonal" block>Sign In</v-btn>
    </template>
    <template v-else-if="sessionStore.authenticated">
      <p class="mb-4">
        You are signed in as {{ sessionStore.session?.user.email }}. Sign out to create a
        new organization with another email address.
      </p>
      <v-btn
        variant="tonal"
        :loading="sessionStore.busy"
        :disabled="sessionStore.busy"
        @click="signOutCurrentAccount">
        Sign Out
      </v-btn>
    </template>
    <template v-else>
      <template v-if="!hasRegistrationLink">
        <v-alert
          v-if="emailMessage"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ emailMessage }}
          <p class="mt-2">Open the verification link in your inbox to continue.</p>
        </v-alert>
        <v-form
          :novalidate="false"
          validate-on="submit"
          @submit.prevent="submitEmailRequest">
          <v-text-field
            v-model="email"
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
            :disabled="isSending"
            required />
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            block
            :loading="isSending"
            :disabled="isSending || intRetrySeconds > 0">
            Send Verification Email
          </v-btn>
        </v-form>
      </template>
      <template v-else>
        <v-progress-linear
          v-if="isChecking"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Checking registration link" />
        <v-form
          v-if="registrationInfo"
          :novalidate="false"
          validate-on="submit"
          @submit.prevent="submitRegistration">
          <v-text-field
            :model-value="registrationInfo.email"
            label="Email"
            autocomplete="username"
            variant="outlined"
            readonly />
          <v-text-field
            v-model="username"
            label="Username"
            autocomplete="nickname"
            variant="outlined"
            maxlength="150"
            hint="Leave blank to generate a username."
            persistent-hint
            :error-messages="requestError?.fields.username ?? []"
            :disabled="isSaving"
            class="mb-3" />
          <PasswordField
            v-model="password"
            label="Password"
            autocomplete="new-password"
            :rules="[validateRequiredPassword]"
            :error-messages="requestError?.fields.password ?? []"
            :disabled="isSaving"
            required />
          <v-text-field
            v-model="organizationName"
            label="Organization Name"
            autocomplete="organization"
            variant="outlined"
            maxlength="200"
            :rules="[validateRequiredOrganizationName]"
            :error-messages="requestError?.fields.organization_name ?? []"
            :disabled="isSaving"
            required />
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            block
            :loading="isSaving"
            :disabled="isSaving || isChecking || intRetrySeconds > 0">
            Create Organization
          </v-btn>
        </v-form>
        <template v-else-if="!isChecking">
          <p class="mb-4">
            Open the link in your verification email. If it has expired, request a new
            verification email.
          </p>
          <v-btn
            v-if="token && requestError?.code !== 'invalid_registration_token'"
            variant="tonal"
            block
            class="mb-3"
            :disabled="intRetrySeconds > 0"
            @click="loadRegistration">
            Check Again
          </v-btn>
          <v-btn :to="{ name: 'create-organization', hash: '' }" variant="tonal" block>
            Request a New Verification Email
          </v-btn>
        </template>
      </template>
      <v-btn
        :to="{ name: 'sign-in' }"
        variant="text"
        class="mt-4"
        :disabled="isSending || isSaving">
        Back to Sign In
      </v-btn>
    </template>
  </AuthLayout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "../layouts/AuthLayout.vue";
import PasswordField from "../components/PasswordField.vue";

import { useSessionStore } from "../stores/sessionStore";
import { useRetryDelay } from "../composables/useRetryDelay";

import { ApiError, getApiError } from "../api/errors";
import {
  requestRegistrationEmail,
  checkRegistration,
  completeRegistration,
} from "../api/registration";
import type { RegistrationInfoResponse } from "../api/registration";

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const hasRegistrationLink = computed(() => route.hash !== "");
const email = ref("");
const emailMessage = ref("");
const token = ref("");
const registrationInfo = shallowRef<RegistrationInfoResponse | null>(null);
const username = ref("");
const password = ref("");
const organizationName = ref("");
const requestError = shallowRef<ApiError | null>(null);
const isSending = ref(false);
const isChecking = ref(false);
const isSaving = ref(false);
const isCreated = ref(false);
let requestRevision = 0;

function validateRequiredEmail(value: string): true | string {
  return value.trim() ? true : "Enter an email address.";
}

function validateRequiredPassword(value: string): true | string {
  return value ? true : "Enter a password.";
}

function validateRequiredOrganizationName(value: string): true | string {
  return value.trim() ? true : "Enter an organization name.";
}

async function submitEmailRequest(event: SubmitEventPromise): Promise<void> {
  if (isSending.value || sessionStore.authenticated || intRetrySeconds.value) return;
  const currentRevision = requestRevision;
  isSending.value = true;
  requestError.value = null;
  emailMessage.value = "";
  try {
    const validation = await event;
    if (!validation.valid || currentRevision !== requestRevision) return;
    const response = await requestRegistrationEmail(email.value.trim());
    if (currentRevision === requestRevision) emailMessage.value = response.message;
  } catch (e) {
    if (currentRevision !== requestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (currentRevision === requestRevision) isSending.value = false;
  }
}

async function loadRegistration(): Promise<void> {
  if (
    !token.value ||
    isChecking.value ||
    isSaving.value ||
    sessionStore.authenticated ||
    intRetrySeconds.value
  )
    return;
  const currentRevision = requestRevision;
  isChecking.value = true;
  requestError.value = null;
  registrationInfo.value = null;
  try {
    const response = await checkRegistration(token.value);
    if (currentRevision === requestRevision) registrationInfo.value = response;
  } catch (e) {
    if (currentRevision !== requestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (currentRevision === requestRevision) isChecking.value = false;
  }
}

async function submitRegistration(event: SubmitEventPromise): Promise<void> {
  if (
    !registrationInfo.value ||
    isChecking.value ||
    isSaving.value ||
    isCreated.value ||
    sessionStore.authenticated ||
    intRetrySeconds.value
  )
    return;
  const currentRevision = requestRevision;
  isSaving.value = true;
  requestError.value = null;
  try {
    const validation = await event;
    if (!validation.valid || currentRevision !== requestRevision) return;
    await completeRegistration({
      token: token.value,
      username: username.value,
      password: password.value,
      organization_name: organizationName.value,
    });
    if (currentRevision !== requestRevision) return;
    isCreated.value = true;
    token.value = "";
    password.value = "";
    registrationInfo.value = null;
    sessionStore.notice = "organization_created";
    await router.replace({ name: "sign-in" });
  } catch (e) {
    if (currentRevision !== requestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (
      ["invalid_registration_token", "email_already_registered"].includes(
        requestError.value.code,
      )
    ) {
      registrationInfo.value = null;
      password.value = "";
    }
  } finally {
    if (currentRevision === requestRevision) isSaving.value = false;
  }
}

async function signOutCurrentAccount(): Promise<void> {
  requestError.value = null;
  try {
    await sessionStore.signOutAccount();
    await loadRegistration();
  } catch (e) {
    requestError.value = getApiError(e);
  }
}

watch(
  () => route.hash,
  () => {
    if (isCreated.value) return;
    requestRevision += 1;
    token.value = "";
    registrationInfo.value = null;
    requestError.value = null;
    emailMessage.value = "";
    username.value = "";
    password.value = "";
    organizationName.value = "";
    isSending.value = false;
    isChecking.value = false;
    isSaving.value = false;
    if (!hasRegistrationLink.value) return;
    const parameters = new URLSearchParams(route.hash.slice(1));
    const linkToken = parameters.get("token") ?? "";
    token.value =
      parameters.getAll("token").length === 1 && /^[A-Za-z0-9_-]{43}$/.test(linkToken)
        ? linkToken
        : "";
    if (!token.value)
      requestError.value = new ApiError("The registration link is missing or invalid.", {
        code: "invalid_registration_token",
      });
    else void loadRegistration();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  requestRevision += 1;
  token.value = "";
  password.value = "";
});
</script>

<style scoped></style>
