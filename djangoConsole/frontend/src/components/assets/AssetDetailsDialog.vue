<!-- FileName: AssetDetailsDialog.vue -->
<template>
  <AssetFormDialog
    v-if="boolEdit && asset"
    mode="edit"
    :asset="asset"
    @close="boolEdit = false"
    @saved="handleSaved" />

  <v-dialog
    :model-value="true"
    :persistent="boolBusy"
    scrollable
    max-width="900"
    aria-labelledby="asset-details-title"
    @update:model-value="!$event && closeDialog()">
    <v-card>
      <v-card-title id="asset-details-title">
        {{ boolConfirmDelete ? "Delete Asset" : "Asset Details" }}
      </v-card-title>

      <v-card-text>
        <v-progress-linear v-if="boolLoading" indeterminate class="mb-4" />

        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
          <p v-if="asset" class="mt-2">
            Previously loaded details are shown and may be out of date.
          </p>
        </v-alert>

        <v-alert
          v-if="strSuccessMessage"
          type="success"
          variant="tonal"
          class="mb-4"
          role="status">
          {{ strSuccessMessage }}
        </v-alert>

        <template v-if="asset">
          <p v-if="boolConfirmDelete" class="text-anywhere mb-4">
            Delete
            <span class="text-highlight font-weight-bold">"{{ asset.path }}"?</span>
            This permanently removes the asset and its value.
          </p>

          <v-alert v-if="boolConfirmDelete" type="warning" variant="tonal" class="mb-4">
            Future Jobs that need this asset will fail to read it. Inputs for Jobs already
            created remain unchanged. Check any references in your flow code as well.
          </v-alert>

          <v-table v-if="boolConfirmDelete && asset.references?.length" class="mb-4">
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

          <dl class="detail-fields">
            <div>
              <dt class="text-caption text-medium-emphasis">Name</dt>
              <dd>{{ asset.name }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Department</dt>
              <dd>{{ asset.department.path }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">Type</dt>
              <dd>{{ getAssetTypeLabel(asset.asset_type) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Updated At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(asset.updated_at, strTimeZone) }}</dd>
            </div>

            <div>
              <dt class="text-caption text-medium-emphasis">
                Created At ({{ strTimeZone }})
              </dt>

              <dd>{{ formatDateTime(asset.created_at, strTimeZone) }}</dd>
            </div>

            <div class="full-width-field">
              <dt class="text-caption text-medium-emphasis">Path</dt>
              <dd>{{ asset.path }}</dd>
            </div>
          </dl>

          <template v-if="!boolConfirmDelete">
            <v-textarea
              class="mt-5"
              :model-value="formatAssetValue(asset)"
              label="Value"
              variant="outlined"
              :rows="isSecretAsset(asset.asset_type) ? 1 : 6"
              readonly
              hide-details />

            <p v-if="isSecretAsset(asset.asset_type)" class="mt-2">
              The stored secret is never displayed.
            </p>

            <v-textarea
              class="mt-5"
              :model-value="asset.notes || '—'"
              label="Notes"
              variant="outlined"
              rows="3"
              readonly
              hide-details />
          </template>
        </template>
      </v-card-text>

      <v-card-actions class="flex-wrap ga-2">
        <template v-if="boolConfirmDelete">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-close"
            :disabled="boolBusy"
            @click="boolConfirmDelete = false">
            Cancel
          </v-btn>
          <v-spacer />
          <v-btn
            color="error"
            variant="tonal"
            prepend-icon="mdi-delete-outline"
            :loading="boolDeleting"
            :disabled="boolBusy"
            @click="submitDelete">
            Delete
          </v-btn>
        </template>

        <template v-else>
          <v-btn
            variant="tonal"
            prepend-icon="mdi-close"
            :disabled="boolBusy"
            @click="closeDialog">
            Close
          </v-btn>

          <v-btn
            v-if="requestError && !boolDeleted"
            variant="tonal"
            prepend-icon="mdi-refresh"
            :disabled="boolBusy"
            @click="loadDetails">
            Retry
          </v-btn>
          <v-spacer />
          <v-btn
            v-if="asset?.can_manage || asset?.can_edit_value"
            variant="tonal"
            prepend-icon="mdi-pencil-outline"
            :disabled="boolBusy || !!requestError"
            @click="openEdit">
            Edit
          </v-btn>

          <v-btn
            v-if="asset?.can_manage"
            color="error"
            variant="tonal"
            prepend-icon="mdi-delete-outline"
            :disabled="boolBusy || !!requestError"
            @click="boolConfirmDelete = true">
            Delete
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import AssetFormDialog from "./AssetFormDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  isSecretAsset,
  getAssetTypeLabel,
  formatAssetValue,
  getAssetDetails,
  deleteAsset,
} from "@/api/assets";
import type {
  AssetDetailsEntryResponse,
  AssetDetailsResponse,
} from "@/api/generated/browserApi";

import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ assetId: string }>();
const emit = defineEmits<{ updated: []; deleted: [] }>();
const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const asset = shallowRef<AssetDetailsEntryResponse | null>(null);
const boolEdit = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const strSuccessMessage = ref("");
const boolLoading = ref(false);
const boolDeleting = ref(false);
const boolConfirmDelete = ref(false);
const boolDeleted = ref(false);
const boolBusy = computed(() => boolLoading.value || boolDeleting.value);
let boolUnmounted = false;

async function loadDetails(): Promise<void> {
  if (boolBusy.value || boolDeleted.value) return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getAssetDetails(props.assetId);
    if (!boolUnmounted) asset.value = response.asset;
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      asset.value = null;
      boolEdit.value = false;
      boolConfirmDelete.value = false;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function closeDialog(): void {
  if (boolBusy.value) return;
  if (boolConfirmDelete.value) {
    boolConfirmDelete.value = false;
    return;
  }
  void router.replace({ name: "assets", query: route.query });
}

function openEdit(): void {
  if (boolBusy.value || !asset.value) return;
  strSuccessMessage.value = "";
  boolEdit.value = true;
}

function handleSaved(response: AssetDetailsResponse): void {
  asset.value = response.asset;
  boolEdit.value = false;
  strSuccessMessage.value = "Asset updated.";
  requestError.value = null;
  emit("updated");
}

async function submitDelete(): Promise<void> {
  if (boolBusy.value || !asset.value?.can_manage) return;
  boolDeleting.value = true;
  requestError.value = null;
  try {
    await deleteAsset(props.assetId);
    if (boolUnmounted) return;
    asset.value = null;
    boolConfirmDelete.value = false;
    boolDeleted.value = true;
    strSuccessMessage.value = "Asset deleted.";
    emit("deleted");
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      asset.value = null;
      boolConfirmDelete.value = false;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolDeleting.value = false;
  }
}

onMounted(() => void loadDetails());

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
