<!-- FileName: AssetDetailsDialog.vue -->
<template>
  <AssetFormDialog
    v-if="editMode && asset"
    :mode="editMode"
    :asset="asset"
    @close="editMode = null"
    @saved="handleSaved" />
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="900"
    aria-labelledby="asset-details-title">
    <v-card>
      <v-card-title id="asset-details-title">{{
        boolConfirmDelete ? "Delete Asset" : "Asset Details"
      }}</v-card-title>
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
          role="status"
          >{{ strSuccessMessage }}</v-alert
        >
        <template v-if="asset">
          <p v-if="boolConfirmDelete" class="mb-4">
            Delete "{{ asset.path }}"? This permanently removes the asset and its value.
          </p>
          <dl class="detail-fields">
            <div>
              <dt>Name</dt>
              <dd>{{ asset.name }}</dd>
            </div>
            <div>
              <dt>Department</dt>
              <dd>{{ asset.department.path }}</dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd>{{ getAssetTypeLabel(asset.asset_type) }}</dd>
            </div>
            <div>
              <dt>Updated At ({{ strTimeZone }})</dt>
              <dd>{{ formatDateTime(asset.updated_at, strTimeZone) }}</dd>
            </div>
            <div>
              <dt>Created At ({{ strTimeZone }})</dt>
              <dd>{{ formatDateTime(asset.created_at, strTimeZone) }}</dd>
            </div>
            <div class="full-width-field">
              <dt>Path</dt>
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
            <!-- TODO: Show authorized Package/Schedule bindings when their models exist; dynamic code references cannot be enumerated. -->
          </template>
        </template>
      </v-card-text>
      <v-card-actions class="flex-wrap ga-2">
        <template v-if="boolConfirmDelete">
          <v-spacer />
          <v-btn variant="text" :disabled="boolBusy" @click="boolConfirmDelete = false"
            >Cancel</v-btn
          >
          <v-btn
            color="error"
            variant="tonal"
            :loading="boolDeleting"
            :disabled="boolBusy"
            @click="submitDelete"
            >Delete</v-btn
          >
        </template>
        <template v-else>
          <v-btn
            v-if="requestError && !boolDeleted"
            variant="text"
            :disabled="boolBusy"
            @click="loadDetails"
            >Retry</v-btn
          >
          <v-btn
            v-if="asset?.can_manage"
            variant="tonal"
            :disabled="boolBusy || !!requestError"
            @click="openEdit('details')"
            >Edit Details</v-btn
          >
          <v-btn
            v-if="asset?.can_edit_value"
            variant="tonal"
            :disabled="boolBusy || !!requestError"
            @click="openEdit('value')"
            >{{ isSecretAsset(asset!.asset_type) ? "Replace Value" : "Edit Value" }}</v-btn
          >
          <v-btn
            v-if="asset?.can_manage"
            color="error"
            variant="tonal"
            :disabled="boolBusy || !!requestError"
            @click="boolConfirmDelete = true"
            >Delete</v-btn
          >
          <v-spacer />
          <v-btn
            :to="{ name: 'assets', query: route.query }"
            replace
            variant="text"
            :disabled="boolBusy"
            >Close</v-btn
          >
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useRoute } from "vue-router";

import AssetFormDialog from "./AssetFormDialog.vue";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import {
  isSecretAsset,
  getAssetTypeLabel,
  formatAssetValue,
  getAssetDetails,
  deleteAsset,
} from "../api/assets";
import type {
  AssetDetailsEntryResponse,
  AssetDetailsResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const props = defineProps<{ assetId: string }>();
const emit = defineEmits<{ updated: []; deleted: [] }>();
const route = useRoute();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const asset = shallowRef<AssetDetailsEntryResponse | null>(null);
const editMode = ref<"details" | "value" | null>(null);
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
      editMode.value = null;
      boolConfirmDelete.value = false;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolLoading.value = false;
  }
}

function openEdit(mode: "details" | "value"): void {
  if (boolBusy.value || !asset.value) return;
  strSuccessMessage.value = "";
  editMode.value = mode;
}

function handleSaved(response: AssetDetailsResponse): void {
  asset.value = response.asset;
  editMode.value = null;
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
