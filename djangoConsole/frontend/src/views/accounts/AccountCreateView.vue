<!-- FileName: AccountCreateView.vue -->
<template>
  <AuthLayout ref="feedbackContainer">
    <v-btn
      v-if="!boolCreated && !sessionStore.authenticated"
      class="mb-4"
      :to="{ name: 'sign-in' }"
      variant="tonal"
      prepend-icon="mdi-arrow-left"
      :disabled="boolSaving">
      Back to Sign In
    </v-btn>

    <h1 class="text-h5 mb-2">Create Account</h1>
    <p class="text-medium-emphasis mb-6">Join the organization that invited you.</p>

    <v-alert
      v-if="requestError"
      ref="errorAlert"
      tabindex="-1"
      type="error"
      variant="tonal"
      class="mb-4"
      role="alert">
      {{ requestError.message }}
      <p v-for="strMessage in requestError.fields.__all__" :key="strMessage" class="mt-2">
        {{ strMessage }}
      </p>

      <p v-if="intRetrySeconds" class="mt-2">Try again in {{ intRetrySeconds }} seconds.</p>
    </v-alert>

    <template v-if="boolCreated">
      <v-alert type="success" variant="tonal" class="mb-4" role="status">
        Account created. Sign in with your invited email address and password.
      </v-alert>

      <v-btn
        :to="{ name: 'sign-in' }"
        color="primary"
        variant="tonal"
        append-icon="mdi-arrow-right"
        block>
        Sign In
      </v-btn>
    </template>

    <template v-else-if="sessionStore.authenticated">
      <p class="text-anywhere mb-4">
        You are signed in as
        <span class="text-highlight font-weight-bold">
          {{ sessionStore.session?.user.email }}.
        </span>
        Sign out to create the invited account.
      </p>

      <div class="d-flex justify-end">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-logout"
          :loading="sessionStore.busy"
          :disabled="sessionStore.busy"
          @click="signOutCurrentAccount">
          Sign Out
        </v-btn>
      </div>
    </template>

    <template v-else>
      <v-progress-linear
        v-if="boolLoading"
        indeterminate
        color="primary"
        class="mb-4"
        aria-label="Checking invitation link" />

      <v-form
        v-if="registrationInfo"
        :novalidate="false"
        validate-on="submit"
        @submit.prevent="submitRegistration">
        <v-text-field
          :model-value="registrationInfo.organization_name"
          label="Organization"
          variant="plain"
          readonly />

        <v-text-field
          :model-value="registrationInfo.email"
          label="Email"
          autocomplete="username"
          variant="plain"
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

        <v-text-field
          v-model="strPassword"
          label="Password"
          autocomplete="new-password"
          variant="outlined"
          :type="boolPasswordVisible ? 'text' : 'password'"
          :rules="[validatePassword]"
          :error-messages="requestError?.fields.password ?? []"
          :disabled="boolSaving"
          required>
          <template #append-inner>
            <v-btn
              type="button"
              variant="text"
              size="small"
              :icon="boolPasswordVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              :aria-label="boolPasswordVisible ? 'Hide password' : 'Show password'"
              :disabled="boolSaving"
              @click="boolPasswordVisible = !boolPasswordVisible" />
          </template>
        </v-text-field>

        <v-btn
          type="submit"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-account-plus-outline"
          block
          :loading="boolSaving"
          :disabled="!boolCanCreate">
          Create Account
        </v-btn>
      </v-form>

      <template v-else-if="!boolLoading">
        <p class="mb-4">
          Open the link in your invitation email. If it has expired or been revoked, ask an
          organization administrator for a new invitation.
        </p>
      </template>

      <v-btn
        v-if="!registrationInfo && !boolLoading && strToken"
        variant="tonal"
        prepend-icon="mdi-refresh"
        class="mt-4"
        :disabled="intRetrySeconds > 0"
        @click="loadInvitation">
        Check Again
      </v-btn>
    </template>
  </AuthLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import AuthLayout from "@/layouts/AuthLayout.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { ApiError, getApiError } from "@/api/errors";
import { checkInvitation, completeInvitation } from "@/api/invitations";
import type { InvitationRegistrationResponse } from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const strToken = ref("");
const strUsername = ref("");
const strPassword = ref("");
const boolPasswordVisible = ref(false);
const registrationInfo = shallowRef<InvitationRegistrationResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolCreated = ref(false);
const boolCanCreate = computed(
  () =>
    !boolLoading.value &&
    !boolSaving.value &&
    !boolCreated.value &&
    !!registrationInfo.value &&
    !sessionStore.authenticated &&
    !intRetrySeconds.value &&
    !!strPassword.value,
);
let intRequestRevision = 0;

async function loadInvitation(): Promise<void> {
  if (
    !strToken.value ||
    boolSaving.value ||
    sessionStore.authenticated ||
    intRetrySeconds.value
  )
    return;
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  registrationInfo.value = null;
  try {
    const response = await checkInvitation(strToken.value);
    if (intCurrentRevision === intRequestRevision) registrationInfo.value = response;
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function validatePassword(value: string): true | string {
  return value ? true : "Enter a password.";
}

async function submitRegistration(event: SubmitEventPromise): Promise<void> {
  if (!boolCanCreate.value) return;
  const intCurrentRevision = intRequestRevision;
  const validation = await event;
  if (intCurrentRevision !== intRequestRevision || !boolCanCreate.value) return;
  if (!validation.valid) {
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el, undefined, true);
    return;
  }
  boolSaving.value = true;
  requestError.value = null;
  try {
    await completeInvitation({
      token: strToken.value,
      username: strUsername.value,
      password: strPassword.value,
    });
    if (intCurrentRevision !== intRequestRevision) return;
    boolCreated.value = true;
    strToken.value = "";
    registrationInfo.value = null;
    sessionStore.notice = "account_created";
    await router.replace({ name: "sign-in" });
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if (
      ["invalid_invitation_token", "email_already_registered"].includes(
        requestError.value.code,
      )
    )
      registrationInfo.value = null;
  } finally {
    if (intCurrentRevision === intRequestRevision) {
      strPassword.value = "";
      boolPasswordVisible.value = false;
      boolSaving.value = false;
      if (requestError.value) {
        await nextTick();
        revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el, true);
      }
    }
  }
}

async function signOutCurrentAccount(): Promise<void> {
  try {
    await sessionStore.signOutAccount();
  } catch (e) {
    requestError.value = getApiError(e);
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el, true);
  }
}

watch(
  () => route.hash,
  () => {
    if (boolCreated.value && !route.hash) return;
    intRequestRevision += 1;
    registrationInfo.value = null;
    requestError.value = null;
    strPassword.value = "";
    strUsername.value = "";
    boolCreated.value = false;
    boolLoading.value = false;
    boolSaving.value = false;
    const parameters = new URLSearchParams(route.hash.slice(1));
    const strLinkToken = parameters.get("token") ?? "";
    strToken.value =
      parameters.getAll("token").length === 1 && /^[A-Za-z0-9_-]{43}$/.test(strLinkToken)
        ? strLinkToken
        : "";
    if (!strToken.value)
      requestError.value = new ApiError("The invitation link is missing or invalid.", {
        code: "invalid_invitation_token",
      });
    else void loadInvitation();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intRequestRevision += 1;
  strToken.value = "";
  strPassword.value = "";
});
</script>

<style scoped></style>
