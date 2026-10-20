<!-- FileName: ServiceSettingsView.vue -->
<template>
  <h1 class="text-h5 mb-6">Service Settings</h1>

  <v-progress-linear
    v-if="boolLoading"
    indeterminate
    color="primary"
    class="mb-4"
    aria-label="Loading service settings" />

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

  <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
    Save was not confirmed. {{ saveError.message }}
    <template v-if="!serviceSettings" #append>
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

  <v-card v-if="serviceSettings" variant="outlined">
    <v-card-text>
      <v-form id="service-settings-form" @submit.prevent="saveSettings">
        <v-switch
          v-model="boolAllowOrganizationCreation"
          label="Allow Organization Creation"
          true-icon="mdi-check"
          color="primary"
          :disabled="boolActionBlocked"
          :error-messages="saveError?.fields.allow_organization_creation ?? []"
          hint="Allow new organizations to be created. Existing accounts and valid invitations are unaffected."
          persistent-hint
          class="mb-6" />

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              :model-value="serviceSettings.console_url"
              label="Console URL"
              variant="underlined"
              hint="Managed in Console.jsonc."
              persistent-hint
              readonly />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              :model-value="serviceSettings.support_email"
              label="Support Email"
              variant="underlined"
              hint="Managed in Console.jsonc."
              persistent-hint
              readonly />
          </v-col>
        </v-row>
      </v-form>
    </v-card-text>

    <v-card-actions>
      <v-spacer />
      <v-btn
        type="submit"
        form="service-settings-form"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-content-save-outline"
        :loading="boolSaving"
        :disabled="boolActionBlocked || !boolChanged">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getServiceSettings, updateServiceSettings } from "@/api/serviceSettings";
import type { ServiceSettingsResponse } from "@/api/generated/browserApi";

const sessionStore = useSessionStore();
const boolCanManage = computed(() => sessionStore.session?.user.is_platform_admin === true);

const serviceSettings = shallowRef<ServiceSettingsResponse | null>(null);
const boolAllowOrganizationCreation = ref(false);
const boolChanged = computed(
  () =>
    serviceSettings.value !== null &&
    boolAllowOrganizationCreation.value !==
      serviceSettings.value.allow_organization_creation,
);

const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolActionBlocked = computed(
  () => boolLoading.value || boolSaving.value || sessionStore.busy || !boolCanManage.value,
);

let boolUnmounted = false;

function applySettings(response: ServiceSettingsResponse): void {
  serviceSettings.value = response;
  boolAllowOrganizationCreation.value = response.allow_organization_creation;
}

async function loadSettings(): Promise<void> {
  if (boolUnmounted || boolActionBlocked.value) return;
  boolLoading.value = true;
  requestError.value = null;
  saveError.value = null;
  strSuccess.value = "";
  try {
    const response = await getServiceSettings();
    if (boolUnmounted) return;
    applySettings(response);
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403].includes(requestError.value.statusCode)) {
      serviceSettings.value = null;
      boolAllowOrganizationCreation.value = false;
    }
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    if (!boolUnmounted) boolLoading.value = false;
  }
}

async function saveSettings(): Promise<void> {
  if (boolUnmounted || boolActionBlocked.value || !boolChanged.value) return;
  boolSaving.value = true;
  saveError.value = null;
  strSuccess.value = "";
  try {
    const response = await updateServiceSettings({
      allow_organization_creation: boolAllowOrganizationCreation.value,
    });
    if (boolUnmounted) return;
    applySettings(response);
    strSuccess.value = "Service settings saved.";
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    if ([401, 403].includes(saveError.value.statusCode)) {
      serviceSettings.value = null;
      boolAllowOrganizationCreation.value = false;
    }
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    if (!boolUnmounted) boolSaving.value = false;
  }
}

onMounted(() => void loadSettings());

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
