<!-- FileName: PlatformTimeZoneDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    max-width="520"
    aria-labelledby="platform-time-zone-title"
    @update:model-value="!$event && closeDialog()">
    <v-card ref="feedbackContainer">
      <v-card-title id="platform-time-zone-title">Time Zone</v-card-title>

      <v-card-text>
        <v-alert
          v-if="saveError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          {{ saveError.message }}
        </v-alert>

        <v-form
          id="platform-time-zone-form"
          validate-on="submit"
          @submit.prevent="saveTimeZone">
          <v-autocomplete
            v-model="strTimeZone"
            :items="arrTimeZone"
            label="Time Zone"
            variant="outlined"
            :rules="[validateTimeZone]"
            :error-messages="saveError?.fields.time_zone ?? []"
            :disabled="boolSaving || sessionStore.busy"
            hint="Used for dates and times displayed in Console."
            persistent-hint
            required />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="closeDialog">
          Cancel
        </v-btn>

        <v-spacer />

        <v-btn
          type="submit"
          form="platform-time-zone-form"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-content-save-outline"
          :loading="boolSaving"
          :disabled="!boolCanSave">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { updatePlatformTimeZone } from "@/api/profile";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const emit = defineEmits<{ close: [] }>();
const sessionStore = useSessionStore();
const strSavedTimeZone = sessionStore.session?.user.time_zone ?? "UTC";
const strTimeZone = ref<string | null>(strSavedTimeZone);
const arrTimeZone = [
  ...new Set(["UTC", strSavedTimeZone, ...Intl.supportedValuesOf("timeZone")]),
].sort();
const boolChanged = computed(() => strTimeZone.value !== strSavedTimeZone);
const saveError = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
const boolCanSave = computed(
  () => !boolSaving.value && !sessionStore.busy && boolChanged.value && !!strTimeZone.value,
);
let boolUnmounted = false;

function validateTimeZone(value: string | null): true | string {
  return value ? true : "Select a time zone.";
}

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function saveTimeZone(event: SubmitEventPromise): Promise<void> {
  if (boolUnmounted || !boolCanSave.value) return;
  const validation = await event;
  if (boolUnmounted || !boolCanSave.value || !strTimeZone.value) return;
  if (!validation.valid) {
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el);
    return;
  }

  boolSaving.value = true;
  saveError.value = null;
  try {
    const response = await updatePlatformTimeZone({ time_zone: strTimeZone.value });
    sessionStore.applyProfileUser(response.user);
    if (!boolUnmounted) emit("close");
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
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
