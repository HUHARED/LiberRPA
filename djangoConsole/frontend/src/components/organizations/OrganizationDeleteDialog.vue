<!-- FileName: OrganizationDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    scrollable
    max-width="640"
    aria-labelledby="organization-delete-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="organization-delete-title">Delete Organization</v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="boolLoading"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Checking organization deletion conditions" />

        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
        </v-alert>

        <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
          Deletion was not confirmed. {{ saveError.message }}
          <p v-if="intRetrySeconds" class="mt-2">
            Try again in {{ intRetrySeconds }} seconds.
          </p>
        </v-alert>

        <v-form
          v-if="deletionInfo?.can_schedule_deletion"
          id="organization-delete-form"
          validate-on="submit"
          @submit.prevent="submitDeletion">
          <v-text-field
            :model-value="deletionInfo.organization.name"
            label="Organization"
            variant="plain"
            readonly />

          <p class="mb-4">
            Business operations stop immediately. After
            {{ deletionInfo.deletion_delay_days }} days, cleanup can permanently delete this
            organization, its current member accounts, and its Console data. Any active
            organization administrator can cancel before cleanup actually starts.
          </p>
          <p class="mb-4">
            This does not delete files on client devices or confirm that remote processes
            have stopped.
          </p>

          <PasswordField
            v-model="strPassword"
            label="Current Password"
            autocomplete="current-password"
            :rules="[validatePassword]"
            :error-messages="saveError?.fields.current_password ?? []"
            :disabled="boolActionBlocked || intRetrySeconds > 0"
            required />
        </v-form>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="closeDialog">
          Cancel
        </v-btn>

        <v-btn
          v-if="requestError || (saveError && !deletionInfo)"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolActionBlocked"
          @click="loadPreview">
          Check Again
        </v-btn>
        <v-spacer />
        <v-btn
          type="submit"
          form="organization-delete-form"
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-clock-outline"
          :loading="boolSaving"
          :disabled="
            boolActionBlocked || !deletionInfo?.can_schedule_deletion || intRetrySeconds > 0
          ">
          Schedule Deletion
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { getOrganizationDeletion, scheduleOrganizationDeletion } from "@/api/organization";
import type { OrganizationDeletionResponse } from "@/api/generated/browserApi";

const emit = defineEmits<{ close: [] }>();
const sessionStore = useSessionStore();
const strActorId = sessionStore.session?.user.id;
const strOrganizationId = sessionStore.access?.organization.id;
const { intRetrySeconds, setRetryDelay } = useRetryDelay();

const deletionInfo = shallowRef<OrganizationDeletionResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strPassword = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    boolSaving.value ||
    sessionStore.busy ||
    sessionStore.session?.user.id !== strActorId ||
    sessionStore.access?.organization.id !== strOrganizationId ||
    !sessionStore.access?.is_org_admin ||
    !sessionStore.access.business_available,
);
let boolUnmounted = false;

async function loadPreview(): Promise<void> {
  if (boolUnmounted || boolActionBlocked.value) return;
  boolLoading.value = true;
  requestError.value = null;
  saveError.value = null;
  deletionInfo.value = null;
  strPassword.value = "";
  try {
    const response = await getOrganizationDeletion();
    if (boolUnmounted) return;
    deletionInfo.value = response;
    if (!response.can_schedule_deletion) await sessionStore.refreshChangedSession();
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function validatePassword(value: string): true | string {
  return value ? true : "Enter your current password.";
}

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function submitDeletion(event: SubmitEventPromise): Promise<void> {
  if (
    boolUnmounted ||
    boolActionBlocked.value ||
    !deletionInfo.value?.can_schedule_deletion ||
    intRetrySeconds.value > 0
  )
    return;
  const validation = await event;
  if (
    !validation.valid ||
    boolUnmounted ||
    boolActionBlocked.value ||
    !deletionInfo.value?.can_schedule_deletion ||
    intRetrySeconds.value > 0
  )
    return;

  boolSaving.value = true;
  saveError.value = null;
  try {
    await scheduleOrganizationDeletion({ current_password: strPassword.value });
    // Invalidate earlier reads and reload access before rendering any business page.
    if (sessionStore.session?.user.id === strActorId)
      await sessionStore.refreshChangedSession();
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    setRetryDelay(saveError.value.retryAfterSeconds);
    if (!saveError.value.fields.current_password && saveError.value.statusCode !== 429)
      deletionInfo.value = null;
    if ([403, 409].includes(saveError.value.statusCode))
      await sessionStore.refreshChangedSession();
  } finally {
    strPassword.value = "";
    boolSaving.value = false;
  }
}

onMounted(() => void loadPreview());
onBeforeUnmount(() => {
  boolUnmounted = true;
  strPassword.value = "";
});
</script>

<style scoped></style>
