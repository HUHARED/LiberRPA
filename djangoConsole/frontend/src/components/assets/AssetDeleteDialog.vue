<!-- FileName: AssetDeleteDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolDeleting"
    scrollable
    max-width="900"
    aria-labelledby="asset-delete-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="asset-delete-title">Delete Asset</v-card-title>

      <v-card-text ref="feedbackContainer">
        <v-progress-linear v-if="boolLoading" indeterminate class="mb-4" />

        <v-alert
          v-if="requestError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          {{ requestError.message }}
        </v-alert>

        <template v-if="asset">
          <p class="text-anywhere mb-4">
            Delete
            <span class="text-highlight font-weight-bold">"{{ asset.path }}"?</span>
            This permanently removes the asset and its value.
          </p>

          <v-alert type="warning" variant="tonal" class="mb-4">
            Future Jobs that need this asset will fail to read it. Inputs for Jobs already
            created remain unchanged. Check any references in your flow code as well.
          </v-alert>

          <v-table v-if="asset.references?.length" class="mb-4">
            <thead>
              <tr>
                <th>Referenced By</th>
                <th>Version</th>
                <th>Type</th>
              </tr>
            </thead>

            <tbody>
              <tr
                v-for="reference in asset.references"
                :key="`${reference.kind}:${reference.id}`">
                <td>
                  <RouterLink
                    :to="{
                      name: reference.kind === 'package' ? 'package-details' : 'schedule',
                      params:
                        reference.kind === 'package'
                          ? { packageId: reference.id }
                          : { scheduleId: reference.id },
                    }"
                    class="text-primary text-decoration-none"
                    target="_blank"
                    rel="noopener">
                    {{ reference.name }}
                  </RouterLink>
                </td>
                <td>{{ reference.project_version || "—" }}</td>
                <td>{{ reference.kind === "package" ? "Package" : "Schedule" }}</td>
              </tr>
            </tbody>
          </v-table>
        </template>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolDeleting"
          @click="closeDialog">
          Cancel
        </v-btn>

        <v-btn
          v-if="requestError"
          variant="tonal"
          prepend-icon="mdi-refresh"
          :disabled="boolBusy"
          @click="loadDetails">
          Retry
        </v-btn>
        <v-spacer />
        <v-btn
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="boolDeleting"
          :disabled="boolBusy || !!requestError || !asset?.can_manage"
          @click="submitDelete">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { nextTick, computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getAssetDetails, deleteAsset } from "@/api/assets";
import type { AssetDetailsEntryResponse } from "@/api/generated/browserApi";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const props = defineProps<{ assetId: string }>();
const emit = defineEmits<{ close: []; deleted: [] }>();
const sessionStore = useSessionStore();
const asset = shallowRef<AssetDetailsEntryResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolDeleting = ref(false);
const boolBusy = computed(() => boolLoading.value || boolDeleting.value);
let boolAlive = true;

async function loadDetails(): Promise<void> {
  if (boolBusy.value) return;
  boolLoading.value = true;
  requestError.value = null;
  asset.value = null;
  try {
    const response = await getAssetDetails(props.assetId);
    if (boolAlive) asset.value = response.asset;
  } catch (e) {
    if (!boolAlive) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    if (boolAlive) boolLoading.value = false;
  }
}

function closeDialog(): void {
  if (!boolDeleting.value) emit("close");
}

async function submitDelete(): Promise<void> {
  if (boolBusy.value || requestError.value || !asset.value?.can_manage) return;
  boolDeleting.value = true;
  try {
    await deleteAsset(props.assetId);
    if (boolAlive) emit("deleted");
  } catch (e) {
    if (!boolAlive) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      asset.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (boolAlive) boolDeleting.value = false;
    if (boolAlive && requestError.value) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

onMounted(() => void loadDetails());

onBeforeUnmount(() => {
  boolAlive = false;
});
</script>

<style scoped></style>
