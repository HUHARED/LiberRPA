<!-- FileName: OrganizationDeletionCancelDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    max-width="560"
    aria-labelledby="organization-deletion-cancel-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="organization-deletion-cancel-title">Cancel Deletion</v-card-title>

      <v-card-text>
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          Cancellation was not confirmed. {{ requestError.message }}
          <p v-if="intRetrySeconds" class="mt-2">
            Try again in {{ intRetrySeconds }} seconds.
          </p>
        </v-alert>

        <p class="mb-4">
          Cancel the deletion of {{ sessionStore.access?.organization.name }}?
        </p>
        <p>
          Any independent service suspension remains in place. Previously canceled work and
          missed scheduled runs do not restart automatically.
        </p>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="closeDialog">
          Keep Deletion Scheduled
        </v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-undo"
          :loading="boolSaving"
          :disabled="!boolCanCancel || boolSaving || intRetrySeconds > 0"
          @click="submitCancellation">
          Cancel Deletion
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { cancelOrganizationDeletion } from "@/api/organization";

const emit = defineEmits<{ close: [] }>();
const sessionStore = useSessionStore();
const strActorId = sessionStore.session?.user.id;
const strOrganizationId = sessionStore.access?.organization.id;
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const boolSaving = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const boolCanCancel = computed(
  () =>
    !sessionStore.busy &&
    sessionStore.session?.user.id === strActorId &&
    sessionStore.access?.organization.id === strOrganizationId &&
    sessionStore.access?.is_org_admin &&
    sessionStore.access.organization.deletion_requested_at !== null &&
    sessionStore.access.organization.deletion_started_at === null,
);
let boolUnmounted = false;

function closeDialog(): void {
  if (!boolSaving.value) emit("close");
}

async function submitCancellation(): Promise<void> {
  if (boolUnmounted || !boolCanCancel.value || boolSaving.value || intRetrySeconds.value)
    return;
  boolSaving.value = true;
  requestError.value = null;
  try {
    await cancelOrganizationDeletion();
    // Reload departments and permissions instead of reusing access from before the freeze.
    if (sessionStore.session?.user.id === strActorId)
      await sessionStore.refreshChangedSession();
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    setRetryDelay(requestError.value.retryAfterSeconds);
    if ([403, 409].includes(requestError.value.statusCode))
      await sessionStore.refreshChangedSession();
  } finally {
    boolSaving.value = false;
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
