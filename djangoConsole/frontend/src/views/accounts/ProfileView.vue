<!-- FileName: ProfileView.vue -->
<template>
  <h1 class="text-h5 mb-4">My Profile</h1>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4" role="status">
    {{ strSuccess }}
  </v-alert>

  <v-card variant="outlined" title="Profile">
    <v-card-text>
      <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
        {{ saveError.message }}
      </v-alert>

      <v-form id="profile-form" validate-on="submit" @submit.prevent="saveProfile">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="strUsername"
              label="Username"
              autocomplete="nickname"
              variant="outlined"
              :maxlength="150"
              :rules="[validateUsername]"
              :error-messages="saveError?.fields.username ?? []"
              :disabled="boolSaving || strActiveAction !== null"
              required />
          </v-col>

          <v-col cols="12" md="6">
            <v-autocomplete
              v-model="strTimeZone"
              label="Time Zone"
              variant="outlined"
              :items="arrTimeZone"
              :rules="[validateTimeZone]"
              :error-messages="saveError?.fields.time_zone ?? []"
              :disabled="boolSaving || strActiveAction !== null"
              hint="Used for dates and times displayed in Console."
              persistent-hint
              required />
          </v-col>
        </v-row>
      </v-form>

      <v-row align="center">
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.session?.user.email"
            label="Email"
            variant="plain"
            hide-details
            readonly />
        </v-col>

        <v-col cols="12" md="6" class="d-flex justify-end">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-email-edit-outline"
            :disabled="boolSaving || sessionStore.busy"
            @click="openAction('email')">
            Change Email
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-actions>
      <v-spacer />
      <v-btn
        type="submit"
        form="profile-form"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-content-save-outline"
        :loading="boolSaving"
        :disabled="
          boolSaving || sessionStore.busy || strActiveAction !== null || !boolChanged
        ">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-card variant="outlined" title="Organization" class="mt-6">
    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.access?.organization.name"
            label="Organization"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>

        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.access?.is_org_admin ? 'OrgAdmin' : 'Member'"
            label="Organization role"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <DepartmentAccess />

  <v-card variant="outlined" title="Account Actions" class="mt-6">
    <v-card-text class="d-flex flex-wrap justify-end ga-3">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-lock-reset"
        :disabled="boolSaving || sessionStore.busy"
        @click="openAction('password')">
        Change Password
      </v-btn>

      <v-btn
        variant="tonal"
        prepend-icon="mdi-logout"
        :disabled="boolSaving || sessionStore.busy"
        @click="openAction('sessions')">
        Sign Out Other Sessions
      </v-btn>
    </v-card-text>
  </v-card>

  <div class="d-flex justify-end mt-6">
    <v-btn
      color="error"
      variant="tonal"
      prepend-icon="mdi-delete-outline"
      :disabled="boolSaving || sessionStore.busy"
      @click="openAction('delete')">
      Delete Account
    </v-btn>
  </div>

  <MemberDeleteDialog
    v-if="strActiveAction === 'delete' && sessionStore.session"
    :user="sessionStore.session.user"
    @close="strActiveAction = null" />

  <AccountActionDialog
    v-else-if="strActiveAction !== null && strActiveAction !== 'delete'"
    :action="strActiveAction"
    @close="strActiveAction = null"
    @completed="completeAction" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import DepartmentAccess from "@/components/organizations/DepartmentAccess.vue";
import AccountActionDialog from "@/components/accounts/AccountActionDialog.vue";
import MemberDeleteDialog from "@/components/organizations/MemberDeleteDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { updateProfile } from "@/api/profile";

const sessionStore = useSessionStore();

// Initialize this draft once so session refreshes and account actions preserve unsaved edits.
const strUsername = ref(sessionStore.session?.user.username ?? "");
const strTimeZone = ref(sessionStore.session?.user.time_zone ?? "UTC");

const arrTimeZone = [
  ...new Set(["UTC", strTimeZone.value, ...Intl.supportedValuesOf("timeZone")]),
].sort();

const savedProfile = ref({ username: strUsername.value, timeZone: strTimeZone.value });

const boolChanged = computed(
  () =>
    strUsername.value !== savedProfile.value.username ||
    strTimeZone.value !== savedProfile.value.timeZone,
);

const strActiveAction = ref<"password" | "sessions" | "email" | "delete" | null>(null);
const strSuccess = ref("");
const saveError = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
let boolUnmounted = false;

function validateUsername(value: string): true | string {
  return value.trim() ? true : "Enter a username.";
}

function validateTimeZone(value: string | null): true | string {
  return value ? true : "Select a time zone.";
}

function openAction(action: NonNullable<typeof strActiveAction.value>): void {
  strSuccess.value = "";
  strActiveAction.value = action;
}

function completeAction(message: string): void {
  strActiveAction.value = null;
  strSuccess.value = message;
}

async function saveProfile(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value || sessionStore.busy || strActiveAction.value || !boolChanged.value)
    return;

  const validation = await event;
  if (
    !validation.valid ||
    boolUnmounted ||
    boolSaving.value ||
    sessionStore.busy ||
    strActiveAction.value
  )
    return;

  boolSaving.value = true;
  saveError.value = null;
  strSuccess.value = "";
  try {
    const response = await updateProfile({
      username: strUsername.value,
      time_zone: strTimeZone.value,
    });
    sessionStore.applyProfileUser(response.user);
    if (boolUnmounted) return;

    strUsername.value = response.user.username;
    strTimeZone.value = response.user.time_zone;
    savedProfile.value = { username: strUsername.value, timeZone: strTimeZone.value };
    strSuccess.value = "Profile saved.";
  } catch (e) {
    if (boolUnmounted) return;

    saveError.value = getApiError(e);
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
