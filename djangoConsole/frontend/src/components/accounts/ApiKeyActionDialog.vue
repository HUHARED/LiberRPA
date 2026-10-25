<!-- FileName: ApiKeyActionDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    scrollable
    max-width="640"
    aria-labelledby="api-key-action-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="api-key-action-title">
        {{ action === "edit" ? "Edit API Key Notes" : "Revoke API Key" }}
      </v-card-title>

      <v-card-text ref="feedbackContainer">
        <v-alert
          v-if="saveError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          The operation was not confirmed. {{ saveError.message }}
          <p v-for="strMessage in saveError.fields.__all__" :key="strMessage" class="mt-2">
            {{ strMessage }}
          </p>

          <p v-if="boolRefreshRequired" class="mt-2">
            Refresh the list to check this key's current state before trying again.
          </p>

          <p v-if="intRetrySeconds" class="mt-2">
            Try again in {{ intRetrySeconds }} seconds.
          </p>
        </v-alert>

        <v-form
          id="api-key-action-form"
          validate-on="submit"
          @submit.prevent="submitAction">
          <v-text-field
            :model-value="`${account.username} (${account.email})`"
            label="Account"
            variant="plain"
            readonly />

          <v-text-field :model-value="apiKey.name" label="Name" variant="plain" readonly />

          <v-textarea
            v-if="action === 'edit'"
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="4"
            maxlength="2000"
            counter="2000"
            :error-messages="saveError?.fields.notes ?? []"
            :disabled="boolSaving || boolRefreshRequired" />

          <template v-else>
            <v-alert type="warning" variant="tonal" class="mb-4">
              Revoking this key is permanent. Further requests using it will be rejected.
            </v-alert>

            <p v-if="strStatus !== 'active'">
              This key is {{ strStatus }} and cannot be revoked.
            </p>
          </template>
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
          v-if="boolRefreshRequired"
          variant="tonal"
          prepend-icon="mdi-refresh"
          @click="emit('refresh')">
          Refresh List
        </v-btn>
        <v-spacer />
        <v-btn
          type="submit"
          form="api-key-action-form"
          :color="action === 'revoke' ? 'error' : 'primary'"
          variant="tonal"
          :prepend-icon="action === 'edit' ? 'mdi-content-save-outline' : 'mdi-cancel'"
          :loading="boolSaving"
          :disabled="boolSubmitBlocked">
          {{ action === "edit" ? "Save" : "Revoke" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { updateApiKeyNotes, revokeApiKey, getApiKeyStatus } from "@/api/apiKeys";
import type { UserResponse, ApiKeyResponse } from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{
  apiKey: ApiKeyResponse;
  action: "edit" | "revoke";
  account: UserResponse;
  asAdministrator: boolean;
}>();

const emit = defineEmits<{ close: []; refresh: []; saved: [apiKey: ApiKeyResponse] }>();
const sessionStore = useSessionStore();
const { intCurrentTimeMs, intRetrySeconds, setRetryDelay } = useRetryDelay();
const strNotes = ref(props.apiKey.notes);
const boolSaving = ref(false);
const saveError = shallowRef<ApiError | null>(null);
const boolRefreshRequired = ref(false);
const strStatus = computed(() => getApiKeyStatus(props.apiKey, intCurrentTimeMs.value));

const boolSubmitBlocked = computed(
  () =>
    boolSaving.value ||
    boolRefreshRequired.value ||
    !sessionStore.authenticated ||
    !sessionStore.access?.business_available ||
    (props.asAdministrator &&
      (!sessionStore.access.is_org_admin || props.action === "edit")) ||
    (!props.asAdministrator && props.account.id !== sessionStore.session?.user.id) ||
    (props.action === "revoke" && strStatus.value !== "active") ||
    intRetrySeconds.value > 0,
);

let boolUnmounted = false;

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function submitAction(event: SubmitEventPromise): Promise<void> {
  if (boolUnmounted || boolSubmitBlocked.value) return;
  const validation = await event;
  if (boolUnmounted || boolSubmitBlocked.value) return;
  if (!validation.valid) {
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el);
    return;
  }
  boolSaving.value = true;
  saveError.value = null;
  try {
    const response =
      props.action === "edit"
        ? await updateApiKeyNotes(props.apiKey.id, strNotes.value)
        : await revokeApiKey(
            props.apiKey.id,
            props.asAdministrator ? props.account.id : undefined,
          );
    if (!boolUnmounted) emit("saved", response.api_key);
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    setRetryDelay(saveError.value.retryAfterSeconds);
    boolRefreshRequired.value =
      [0, 401, 403, 404, 409].includes(saveError.value.statusCode) ||
      saveError.value.statusCode >= 500 ||
      saveError.value.code === "invalid_response";
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
    if (!boolUnmounted && saveError.value) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
