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

    <template v-if="boolCreated">
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
      <template v-if="!boolHasRegistrationLink">
        <v-alert
          v-if="strEmailMessage"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ strEmailMessage }}
          <p class="mt-2">Open the verification link in your inbox to continue.</p>
        </v-alert>

        <v-form
          :novalidate="false"
          validate-on="submit"
          @submit.prevent="submitEmailRequest">
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
            block
            :loading="boolSending"
            :disabled="boolSending || intRetrySeconds > 0">
            Send Verification Email
          </v-btn>
        </v-form>
      </template>

      <template v-else>
        <v-progress-linear
          v-if="boolChecking"
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
            v-model="strUsername"
            label="Username"
            autocomplete="nickname"
            variant="outlined"
            maxlength="150"
            hint="Leave blank to generate a username."
            persistent-hint
            :error-messages="requestError?.fields.username ?? []"
            :disabled="boolSaving"
            class="mb-3" />

          <PasswordField
            v-model="strPassword"
            label="Password"
            autocomplete="new-password"
            :rules="[validateRequiredPassword]"
            :error-messages="requestError?.fields.password ?? []"
            :disabled="boolSaving"
            required />

          <v-text-field
            v-model="strOrganizationName"
            label="Organization Name"
            autocomplete="organization"
            variant="outlined"
            maxlength="200"
            :rules="[validateRequiredOrganizationName]"
            :error-messages="requestError?.fields.organization_name ?? []"
            :disabled="boolSaving"
            required />

          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            block
            :loading="boolSaving"
            :disabled="boolSaving || boolChecking || intRetrySeconds > 0">
            Create Organization
          </v-btn>
        </v-form>

        <template v-else-if="!boolChecking">
          <p class="mb-4">
            Open the link in your verification email. If it has expired, request a new
            verification email.
          </p>
          <v-btn
            v-if="strToken && requestError?.code !== 'invalid_registration_token'"
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
        :disabled="boolSending || boolSaving">
        Back to Sign In
      </v-btn>
    </template>
  </AuthLayout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "@/layouts/AuthLayout.vue";
import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

import { ApiError, getApiError } from "@/api/errors";
import {
  requestRegistrationEmail,
  checkRegistration,
  completeRegistration,
} from "@/api/registration";
import type { RegistrationInfoResponse } from "@/api/registration";

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const boolHasRegistrationLink = computed(() => route.hash !== "");
const strEmail = ref("");
const strEmailMessage = ref("");
const strToken = ref("");
const registrationInfo = shallowRef<RegistrationInfoResponse | null>(null);
const strUsername = ref("");
const strPassword = ref("");
const strOrganizationName = ref("");
const requestError = shallowRef<ApiError | null>(null);
const boolSending = ref(false);
const boolChecking = ref(false);
const boolSaving = ref(false);
const boolCreated = ref(false);
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
  if (boolSending.value || sessionStore.authenticated || intRetrySeconds.value) return;

  const intCurrentRevision = requestRevision;
  boolSending.value = true;
  requestError.value = null;
  strEmailMessage.value = "";
  try {
    const validation = await event;
    if (!validation.valid || intCurrentRevision !== requestRevision) return;

    const response = await requestRegistrationEmail(strEmail.value.trim());
    if (intCurrentRevision === requestRevision) strEmailMessage.value = response.message;
  } catch (e) {
    if (intCurrentRevision !== requestRevision) return;

    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (intCurrentRevision === requestRevision) boolSending.value = false;
  }
}

async function loadRegistration(): Promise<void> {
  if (
    !strToken.value ||
    boolChecking.value ||
    boolSaving.value ||
    sessionStore.authenticated ||
    intRetrySeconds.value
  )
    return;

  const intCurrentRevision = requestRevision;
  boolChecking.value = true;
  requestError.value = null;
  registrationInfo.value = null;
  try {
    const response = await checkRegistration(strToken.value);
    if (intCurrentRevision === requestRevision) registrationInfo.value = response;
  } catch (e) {
    if (intCurrentRevision !== requestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (intCurrentRevision === requestRevision) boolChecking.value = false;
  }
}

async function submitRegistration(event: SubmitEventPromise): Promise<void> {
  if (
    !registrationInfo.value ||
    boolChecking.value ||
    boolSaving.value ||
    boolCreated.value ||
    sessionStore.authenticated ||
    intRetrySeconds.value
  )
    return;

  const intCurrentRevision = requestRevision;
  boolSaving.value = true;
  requestError.value = null;
  try {
    const validation = await event;
    if (!validation.valid || intCurrentRevision !== requestRevision) return;

    await completeRegistration({
      token: strToken.value,
      username: strUsername.value,
      password: strPassword.value,
      organization_name: strOrganizationName.value,
    });
    if (intCurrentRevision !== requestRevision) return;

    boolCreated.value = true;
    strToken.value = "";
    strPassword.value = "";
    registrationInfo.value = null;
    sessionStore.notice = "organization_created";
    await router.replace({ name: "sign-in" });
  } catch (e) {
    if (intCurrentRevision !== requestRevision) return;

    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (
      ["invalid_registration_token", "email_already_registered"].includes(
        requestError.value.code,
      )
    ) {
      registrationInfo.value = null;
      strPassword.value = "";
    }
  } finally {
    if (intCurrentRevision === requestRevision) boolSaving.value = false;
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
    if (boolCreated.value) return;

    requestRevision += 1;
    strToken.value = "";
    registrationInfo.value = null;
    requestError.value = null;
    strEmailMessage.value = "";
    strUsername.value = "";
    strPassword.value = "";
    strOrganizationName.value = "";
    boolSending.value = false;
    boolChecking.value = false;
    boolSaving.value = false;
    if (!boolHasRegistrationLink.value) return;

    const parameters = new URLSearchParams(route.hash.slice(1));
    const linkToken = parameters.get("token") ?? "";
    strToken.value =
      parameters.getAll("token").length === 1 && /^[A-Za-z0-9_-]{43}$/.test(linkToken)
        ? linkToken
        : "";
    if (!strToken.value)
      requestError.value = new ApiError("The registration link is missing or invalid.", {
        code: "invalid_registration_token",
      });
    else void loadRegistration();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  requestRevision += 1;
  strToken.value = "";
  strPassword.value = "";
});
</script>

<style scoped></style>
