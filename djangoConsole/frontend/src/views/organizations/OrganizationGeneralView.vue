<!-- FileName: OrganizationGeneralView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">General</h2>
    <v-btn
      color="error"
      variant="tonal"
      prepend-icon="mdi-delete-outline"
      :disabled="boolActionBlocked || !organizationInfo"
      @click="boolShowDeletion = true">
      Delete Organization
    </v-btn>
  </div>

  <v-progress-linear
    v-if="boolLoading"
    indeterminate
    color="primary"
    class="mb-4"
    aria-label="Loading organization settings" />

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <template #append>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadSettings">
        Retry
      </v-btn>
    </template>
  </v-alert>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4" role="status">
    {{ strSuccess }}
  </v-alert>

  <v-card v-if="organizationInfo" ref="feedbackContainer" variant="outlined">
    <v-card-text>
      <v-alert
        v-if="saveError"
        ref="errorAlert"
        tabindex="-1"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        Save was not confirmed. {{ saveError.message }}
      </v-alert>

      <v-form
        id="organization-general-form"
        validate-on="submit"
        @submit.prevent="saveSettings">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="strName"
              label="Name"
              autocomplete="organization"
              variant="outlined"
              :maxlength="200"
              :rules="[validateName]"
              :error-messages="saveError?.fields.name ?? []"
              :disabled="boolActionBlocked"
              required />
          </v-col>

          <v-col cols="12" md="6">
            <v-autocomplete
              v-model="strDefaultTimeZone"
              label="Default Time Zone"
              variant="outlined"
              :items="arrTimeZone"
              :rules="[validateTimeZone]"
              :error-messages="saveError?.fields.default_time_zone ?? []"
              :disabled="boolActionBlocked"
              hint="Used for email timestamps and new members' initial time zone. New schedules use your personal time zone."
              persistent-hint
              required />
          </v-col>

          <v-col cols="12">
            <v-textarea
              v-model="strNotes"
              label="Notes"
              variant="outlined"
              rows="4"
              auto-grow
              :maxlength="2000"
              :counter="2000"
              :error-messages="saveError?.fields.notes ?? []"
              :disabled="boolActionBlocked" />
          </v-col>
        </v-row>
      </v-form>
    </v-card-text>

    <v-card-actions>
      <v-spacer />
      <v-btn
        type="submit"
        form="organization-general-form"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-content-save-outline"
        :loading="boolSaving"
        :disabled="boolActionBlocked || !boolChanged || !boolRequiredFieldsComplete">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>

  <OrganizationDeleteDialog
    v-if="boolShowDeletion && boolCanManage"
    @close="boolShowDeletion = false" />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import OrganizationDeleteDialog from "@/components/organizations/OrganizationDeleteDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getOrganizationSettings, updateOrganizationSettings } from "@/api/organization";
import type { OrganizationSettingsRecordResponse } from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const sessionStore = useSessionStore();

const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);

const organizationInfo = shallowRef<OrganizationSettingsRecordResponse | null>(null);
const strName = ref("");
const strDefaultTimeZone = ref("UTC");
const strNotes = ref("");

const arrTimeZone = computed(() =>
  [
    ...new Set([
      "UTC",
      organizationInfo.value?.default_time_zone ?? "UTC",
      ...Intl.supportedValuesOf("timeZone"),
    ]),
  ].sort(),
);

const boolChanged = computed(
  () =>
    organizationInfo.value !== null &&
    (strName.value !== organizationInfo.value.name ||
      strDefaultTimeZone.value !== organizationInfo.value.default_time_zone ||
      strNotes.value !== organizationInfo.value.notes),
);

const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolShowDeletion = ref(false);

const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    boolSaving.value ||
    boolShowDeletion.value ||
    sessionStore.busy ||
    !boolCanManage.value,
);

let boolUnmounted = false;

function applySettings(organization: OrganizationSettingsRecordResponse): void {
  organizationInfo.value = organization;
  strName.value = organization.name;
  strDefaultTimeZone.value = organization.default_time_zone;
  strNotes.value = organization.notes;
}

const boolRequiredFieldsComplete = computed(
  () => !!strName.value.trim() && !!strDefaultTimeZone.value,
);

async function loadSettings(): Promise<void> {
  if (boolUnmounted || boolActionBlocked.value) return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getOrganizationSettings();
    if (boolUnmounted) return;
    applySettings(response.organization);
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function validateName(value: string): true | string {
  return value.trim() ? true : "Enter an organization name.";
}

function validateTimeZone(value: string | null): true | string {
  return value ? true : "Select a time zone.";
}

async function saveSettings(event: SubmitEventPromise): Promise<void> {
  if (
    !boolRequiredFieldsComplete.value ||
    boolUnmounted ||
    boolActionBlocked.value ||
    !boolChanged.value
  )
    return;
  const validation = await event;
  if (!validation.valid) {
    await nextTick();
    if (!boolUnmounted) revealFormFeedback(feedbackContainer.value?.$el, undefined, true);
    return;
  }
  if (boolUnmounted || boolActionBlocked.value || !boolChanged.value) return;
  boolSaving.value = true;
  saveError.value = null;
  strSuccess.value = "";
  try {
    const response = await updateOrganizationSettings({
      name: strName.value,
      default_time_zone: strDefaultTimeZone.value,
      notes: strNotes.value,
    });
    sessionStore.applyOrganizationName(
      response.organization.id,
      response.organization.name,
    );
    if (boolUnmounted) return;
    applySettings(response.organization);
    strSuccess.value = "Organization settings saved.";
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
    if (saveError.value && !boolUnmounted) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el, true);
    }
  }
}

onMounted(() => void loadSettings());

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
