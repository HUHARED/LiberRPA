<!-- FileName: ApiKeyCreateDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="680"
    aria-labelledby="api-key-create-title">
    <v-card>
      <v-card-title id="api-key-create-title">
        {{ createdKey ? "API Key Created" : "New API Key" }}
      </v-card-title>
      <v-card-text>
        <template v-if="createdKey">
          <v-alert type="success" variant="tonal" class="text-anywhere mb-4" role="status">
            API key
            <span class="font-weight-bold">{{ createdKey.name }}</span>
            created.
          </v-alert>
          <p class="mb-4">
            Copy and save this key now. You won't be able to view it again.
          </p>
          <v-textarea
            :model-value="strSecret"
            label="API Key"
            variant="outlined"
            rows="3"
            readonly
            spellcheck="false"
            autocomplete="off" />
          <p v-if="boolCopied" class="text-success" role="status">Copied.</p>
          <p v-if="strCopyError" class="text-error" role="alert">
            {{ strCopyError }}
          </p>
        </template>
        <v-form
          v-else
          id="api-key-create-form"
          :novalidate="false"
          validate-on="submit"
          @submit.prevent="submitCreate">
          <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
            Creation was not confirmed. {{ saveError.message }}
            <p
              v-for="strMessage in saveError.fields.__all__"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
            </p>
            <p
              v-for="strMessage in saveError.fields.time_zone"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
            </p>
            <p v-if="boolUncertain" class="mt-2">
              Check the list before creating another key. If a key was created without
              displaying its secret, revoke it and create a replacement.
            </p>
            <p v-if="intRetrySeconds" class="mt-2">
              Try again in {{ intRetrySeconds }} seconds.
            </p>
          </v-alert>
          <v-text-field
            v-model="strName"
            label="Name"
            variant="outlined"
            maxlength="100"
            :rules="[validateName]"
            :error-messages="saveError?.fields.name ?? []"
            :disabled="boolSaving || boolUncertain"
            required />
          <v-text-field
            v-model="strExpiresAt"
            :label="`Expires At (${strTimeZone})`"
            type="datetime-local"
            variant="outlined"
            :rules="[validateExpiry]"
            :error-messages="saveError?.fields.expires_at ?? []"
            :disabled="boolSaving || boolUncertain"
            required />
          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            maxlength="2000"
            counter="2000"
            :error-messages="saveError?.fields.notes ?? []"
            :disabled="boolSaving || boolUncertain" />
          <p>
            API keys perform Operator actions within your current department access. Your
            account can have up to
            <span class="font-weight-bold">{{ activeKeyLimit }}</span>
            active keys.
          </p>
        </v-form>
      </v-card-text>
      <v-card-actions class="flex-wrap ga-2">
        <v-spacer />
        <template v-if="createdKey">
          <v-btn variant="tonal" :loading="boolCopying" @click="copySecret">Copy</v-btn>
          <v-btn color="primary" variant="tonal" @click="finishCreation">Done</v-btn>
        </template>
        <template v-else>
          <v-btn variant="tonal" :disabled="boolSaving" @click="closeDialog">Cancel</v-btn>
          <v-btn v-if="boolUncertain" variant="tonal" @click="emit('refresh')">
            Check List
          </v-btn>
          <v-btn
            v-else
            type="submit"
            form="api-key-create-form"
            color="primary"
            variant="tonal"
            :loading="boolSaving"
            :disabled="boolSubmitBlocked">
            Create
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { createApiKey } from "@/api/apiKeys";
import type { ApiKeyResponse } from "@/api/generated/browserApi";
import { formatDateTimeInput } from "@/app/formatters";

const props = defineProps<{ defaultExpiresAt: string; activeKeyLimit: number }>();
const emit = defineEmits<{ close: []; refresh: []; created: [apiKey: ApiKeyResponse] }>();
const sessionStore = useSessionStore();
// Keep the draft's zone stable even if the profile changes in another tab.
const strTimeZone = sessionStore.session?.user.time_zone ?? "UTC";
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const strName = ref("");
const strExpiresAt = ref(
  `${formatDateTimeInput(props.defaultExpiresAt, strTimeZone).slice(0, 10)}T00:00`,
);
const strNotes = ref("");
const strSecret = ref("");
const createdKey = shallowRef<ApiKeyResponse | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
const boolUncertain = ref(false);
const boolCopied = ref(false);
const boolCopying = ref(false);
const strCopyError = ref("");
const boolSubmitBlocked = computed(
  () =>
    boolSaving.value ||
    boolUncertain.value ||
    createdKey.value !== null ||
    !sessionStore.authenticated ||
    !sessionStore.access?.business_available ||
    intRetrySeconds.value > 0,
);
let boolUnmounted = false;

function validateName(value: string): true | string {
  return value.trim() ? true : "Enter a name.";
}

function validateExpiry(value: string): true | string {
  return value ? true : "Choose an expiry date and time.";
}

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function submitCreate(event: SubmitEventPromise): Promise<void> {
  if (boolUnmounted || boolSubmitBlocked.value) return;
  const validation = await event;
  if (!validation.valid || boolUnmounted || boolSubmitBlocked.value) return;
  boolSaving.value = true;
  saveError.value = null;
  try {
    const response = await createApiKey({
      name: strName.value.trim(),
      expires_at: strExpiresAt.value,
      notes: strNotes.value,
      time_zone: strTimeZone,
    });
    if (boolUnmounted) return;
    createdKey.value = response.api_key;
    strSecret.value = response.secret;
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    setRetryDelay(saveError.value.retryAfterSeconds);
    boolUncertain.value =
      saveError.value.statusCode === 0 ||
      saveError.value.statusCode >= 500 ||
      saveError.value.code === "invalid_response";
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

async function copySecret(): Promise<void> {
  if (!strSecret.value || boolCopying.value) return;
  boolCopying.value = true;
  strCopyError.value = "";
  try {
    await navigator.clipboard.writeText(strSecret.value);
    if (!boolUnmounted) boolCopied.value = true;
  } catch {
    if (!boolUnmounted)
      strCopyError.value = "Copy failed. Select the key and copy it manually.";
  } finally {
    boolCopying.value = false;
  }
}

function finishCreation(): void {
  if (!createdKey.value) return;
  strSecret.value = "";
  emit("created", createdKey.value);
}

onBeforeUnmount(() => {
  boolUnmounted = true;
  strSecret.value = "";
});
</script>

<style scoped></style>
