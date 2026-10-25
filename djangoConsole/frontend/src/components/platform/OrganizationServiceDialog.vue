<!-- FileName: OrganizationServiceDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving || boolLoading"
    max-width="720"
    scrollable
    aria-labelledby="organization-service-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="organization-service-title">
        {{ boolSuspend ? "Suspend Service" : "Resume Service" }}
      </v-card-title>

      <v-card-text ref="feedbackContainer">
        <v-text-field
          :model-value="organization.name"
          label="Organization"
          variant="plain"
          readonly
          hide-details
          class="mb-4" />

        <v-text-field
          :model-value="organization.id"
          label="Organization ID"
          variant="plain"
          readonly
          hide-details
          class="mb-4" />

        <v-alert :type="boolSuspend ? 'warning' : 'info'" variant="tonal" class="mb-4">
          <template v-if="boolSuspend">
            Suspend all Console business requests for this organization, including Executor
            heartbeats and result reports. Waiting work will not resume after service is
            restored. Running processes may continue on their computers.
          </template>
          <template v-else>
            Allow eligible new business requests. Previously canceled work and missed
            Schedule triggers will not run again. A scheduled organization deletion will
            remain in place.
          </template>
        </v-alert>

        <v-alert
          v-if="saveError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          {{ saveError.message }}
          <div v-if="boolRefreshRequired" class="mt-3">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              :loading="boolLoading"
              :disabled="boolSaving || boolLoading"
              @click="loadOrganization()">
              Refresh Organization
            </v-btn>
          </div>
        </v-alert>

        <v-alert v-if="strServiceUnavailable" type="info" variant="tonal" class="mb-4">
          {{ strServiceUnavailable }}
        </v-alert>

        <v-form id="organization-service-form" @submit.prevent="saveService">
          <v-textarea
            v-model="strReason"
            label="Reason"
            variant="outlined"
            rows="3"
            auto-grow
            :counter="INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH"
            :counter-value="(value) => Array.from(value).length"
            :error-messages="saveError?.fields.reason ?? []"
            :disabled="
              boolSaving || boolLoading || boolRefreshRequired || !!strServiceUnavailable
            "
            hint="Recorded in the platform audit log. Not included in the email to administrators."
            persistent-hint />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving || boolLoading"
          @click="closeDialog">
          Cancel
        </v-btn>

        <v-spacer />

        <v-btn
          type="submit"
          form="organization-service-form"
          :color="boolSuspend ? 'warning' : 'primary'"
          variant="tonal"
          :prepend-icon="
            boolSuspend ? 'mdi-pause-circle-outline' : 'mdi-play-circle-outline'
          "
          :loading="boolSaving"
          :disabled="
            boolSaving ||
            boolLoading ||
            boolRefreshRequired ||
            !!strServiceUnavailable ||
            !strReason.trim()
          ">
          {{ boolSuspend ? "Suspend Service" : "Resume Service" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { ApiError, getApiError } from "@/api/errors";
import {
  getPlatformOrganizationDetails,
  updateOrganizationService,
} from "@/api/platformOrganizations";
import {
  INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH,
  type PlatformOrganizationDetailsResponse,
} from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{ organization: PlatformOrganizationDetailsResponse }>();
const emit = defineEmits<{
  close: [];
  refreshed: [organization: PlatformOrganizationDetailsResponse];
  saved: [organization: PlatformOrganizationDetailsResponse];
  unavailable: [error: ApiError];
}>();

const sessionStore = useSessionStore();
const boolHasAccess = computed(() => !!sessionStore.session?.user.is_platform_admin);

const organization = shallowRef(props.organization);
const boolSuspend = props.organization.suspended_at === null;
const strReason = ref("");
const saveError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolRefreshRequired = ref(false);
const strServiceUnavailable = computed(() => {
  if (organization.value.deletion_started_at)
    return "Organization deletion is in progress.";
  if ((organization.value.suspended_at !== null) === boolSuspend)
    return boolSuspend ? "Service is already suspended." : "Service is already resumed.";
  return "";
});
let boolUnmounted = false;

function closeDialog(): void {
  if (!boolLoading.value && !boolSaving.value) emit("close");
}

async function loadOrganization(): Promise<void> {
  if (boolUnmounted || !boolHasAccess.value || boolLoading.value || boolSaving.value)
    return;
  boolLoading.value = true;
  saveError.value = null;
  try {
    const response = await getPlatformOrganizationDetails(organization.value.id);
    if (boolUnmounted || !boolHasAccess.value) return;
    organization.value = response;
    boolRefreshRequired.value = false;
    emit("refreshed", response);
  } catch (e) {
    if (boolUnmounted || !boolHasAccess.value) return;
    const error = getApiError(e);
    saveError.value = error;
    if ([401, 403, 404].includes(error.statusCode)) emit("unavailable", error);
  } finally {
    boolLoading.value = false;
  }
}

async function saveService(): Promise<void> {
  if (
    boolUnmounted ||
    !boolHasAccess.value ||
    boolLoading.value ||
    boolSaving.value ||
    boolRefreshRequired.value ||
    strServiceUnavailable.value ||
    !strReason.value.trim()
  )
    return;
  const strTrimmedReason = strReason.value.trim();
  if (
    !strTrimmedReason ||
    Array.from(strTrimmedReason).length > INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH
  ) {
    saveError.value = new ApiError("Enter a reason for this change.", {
      fields: {
        reason: [`Enter 1 to ${INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH} characters.`],
      },
    });
    await nextTick();
    revealFormFeedback(feedbackContainer.value?.$el);
    return;
  }

  boolSaving.value = true;
  saveError.value = null;
  try {
    const response = await updateOrganizationService(organization.value.id, {
      suspended: boolSuspend,
      reason: strTrimmedReason,
      expected_suspended_at: organization.value.suspended_at,
      expected_deletion_requested_at: organization.value.deletion_requested_at,
    });
    if (boolUnmounted || !boolHasAccess.value) return;
    emit("saved", response);
  } catch (e) {
    if (boolUnmounted || !boolHasAccess.value) return;
    const error = getApiError(e);
    saveError.value = error;
    if (error.code === "organization_state_changed") boolRefreshRequired.value = true;
    if (
      error.code === "organization_deleting" ||
      [401, 403, 404].includes(error.statusCode)
    )
      emit("unavailable", error);
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
