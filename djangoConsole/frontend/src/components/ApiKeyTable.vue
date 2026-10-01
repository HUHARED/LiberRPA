<!-- FileName: ApiKeyTable.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col cols="12" sm="6" md="5">
      <v-select
        :model-value="arrStatus"
        :items="ARR_STATUS_OPTION"
        label="Status"
        variant="outlined"
        multiple
        chips
        clearable
        hint="No selection shows all statuses."
        persistent-hint
        :disabled="boolDialogOpen || !boolCanManage"
        @update:model-value="changeStatusFilter" />
    </v-col>

    <v-spacer v-if="!member" />

    <v-col v-if="!member" cols="auto">
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="boolActionBlocked || keyList === null"
        @click="openCreation">
        New API Key
      </v-btn>
    </v-col>
  </v-row>

  <v-alert
    v-if="strSuccessMessage"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    {{ strSuccessMessage }}
  </v-alert>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}

    <p v-if="keyList" class="mt-2">
      Previously loaded keys are shown and may be out of date.
    </p>

    <template #append>
      <v-btn
        variant="tonal"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadApiKeys">
        Retry
      </v-btn>
    </template>
  </v-alert>

  <p v-if="keyList" class="mb-3">
    Active key limit: {{ keyList.limits.active_keys }} per account.
    <template
      v-if="keyList.limits.inactive_retention_days && keyList.limits.inactive_records">
      Expired and revoked records are kept for at most
      {{ keyList.limits.inactive_retention_days }} days, up to the most recent
      {{ keyList.limits.inactive_records }} records.
    </template>

    <template v-else>Expired and revoked records are not retained.</template>

    Inactive keys do not count toward the active key limit.
  </p>

  <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
    Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
  </p>

  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table
      :headers="arrHeader"
      :items="arrVisibleKey"
      :items-per-page="50"
      :items-per-page-options="[50]"
      :hide-default-footer="arrVisibleKey.length <= 50"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="id"
      disable-sort
      loading-text="Loading API keys…">
      <template #item.name="{ item }">
        <span class="table-text">{{ item.name }}</span>
      </template>

      <template #item.status="{ item }">
        <span class="text-capitalize">{{ getApiKeyStatus(item, intCurrentTimeMs) }}</span>
      </template>

      <template #item.expires_at="{ item }">
        {{ formatDateTime(item.expires_at, strTimeZone) }}
      </template>

      <template #item.last_used_at="{ item }">
        {{ formatDateTime(item.last_used_at, strTimeZone) }}
      </template>

      <template #item.notes="{ item }">
        <p class="table-text text-pre-wrap">{{ item.notes || "—" }}</p>
      </template>

      <template #item.actions="{ item }">
        <v-btn
          v-if="!member"
          variant="text"
          size="small"
          :disabled="boolActionBlocked"
          :aria-label="`Edit Notes for API key ${item.name}`"
          @click="openAction(item, 'edit')">
          Edit Notes
        </v-btn>

        <v-btn
          v-if="getApiKeyStatus(item, intCurrentTimeMs) === 'active'"
          color="error"
          variant="text"
          size="small"
          :disabled="boolActionBlocked"
          :aria-label="`Revoke API key ${item.name}`"
          @click="openAction(item, 'revoke')">
          Revoke
        </v-btn>
      </template>

      <template #no-data>
        {{
          requestError ? "The API key list could not be loaded." : "No matching API keys."
        }}
      </template>
    </v-data-table>
  </v-card>

  <ApiKeyCreateDialog
    v-if="boolCreating && keyList"
    :default-expires-at="keyList.default_expires_at"
    :active-key-limit="keyList.limits.active_keys"
    @close="boolCreating = false"
    @refresh="closeAndRefresh"
    @created="handleCreated" />

  <ApiKeyActionDialog
    v-if="selectedKey && account"
    :api-key="selectedKey.apiKey"
    :action="selectedKey.action"
    :account="account"
    :as-administrator="member !== undefined"
    @close="selectedKey = null"
    @refresh="closeAndRefresh"
    @saved="handleSaved" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

import ApiKeyCreateDialog from "./ApiKeyCreateDialog.vue";
import ApiKeyActionDialog from "./ApiKeyActionDialog.vue";

import { useSessionStore } from "../stores/sessionStore";
import { useRetryDelay } from "../composables/useRetryDelay";

import { type ApiError, getApiError } from "../api/errors";
import { type ApiKeyStatus, getApiKeyList, getApiKeyStatus } from "../api/apiKeys";
import type {
  UserResponse,
  ApiKeyResponse,
  ApiKeyListResponse,
} from "../api/generated/browserApi";
import { formatDateTime } from "../app/formatters";

const props = defineProps<{ member?: UserResponse }>();
const ARR_STATUS_OPTION = [
  { title: "Active", value: "active" },
  { title: "Expired", value: "expired" },
  { title: "Revoked", value: "revoked" },
];

const sessionStore = useSessionStore();
const account = computed(() => props.member ?? sessionStore.session?.user);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolCanManage = computed(
  () =>
    sessionStore.authenticated &&
    sessionStore.access?.business_available &&
    (!props.member || sessionStore.access.is_org_admin),
);
const { intCurrentTimeMs } = useRetryDelay();
const arrStatus = ref<ApiKeyStatus[]>(["active", "expired", "revoked"]);
const arrHeader = computed(() => [
  { title: "Name", key: "name", minWidth: 180 },
  { title: "Status", key: "status", minWidth: 100 },
  { title: `Expires At (${strTimeZone.value})`, key: "expires_at", minWidth: 240 },
  { title: `Last Used At (${strTimeZone.value})`, key: "last_used_at", minWidth: 240 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: "Actions", key: "actions", width: props.member ? 120 : 230 },
]);
const keyList = shallowRef<ApiKeyListResponse | null>(null);
const arrVisibleKey = computed(() =>
  (keyList.value?.api_keys ?? []).filter(
    (apiKey) =>
      !arrStatus.value.length ||
      arrStatus.value.includes(getApiKeyStatus(apiKey, intCurrentTimeMs.value)),
  ),
);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const boolCreating = ref(false);
const selectedKey = shallowRef<{
  apiKey: ApiKeyResponse;
  action: "edit" | "revoke";
} | null>(null);
const boolDialogOpen = computed(() => boolCreating.value || selectedKey.value !== null);
const boolActionBlocked = computed(
  () => boolLoading.value || boolDialogOpen.value || !boolCanManage.value,
);
const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;

async function loadApiKeys(): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getApiKeyList(arrStatus.value, props.member?.id);
    if (intCurrentRevision !== intRequestRevision) return;

    keyList.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;

    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      keyList.value = null;
      strUpdatedAt.value = null;
      boolCreating.value = false;
      selectedKey.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function changeStatusFilter(statuses: ApiKeyStatus[]): void {
  if (boolDialogOpen.value || !boolCanManage.value) return;

  arrStatus.value = statuses;
  keyList.value = null;
  strUpdatedAt.value = null;
  void loadApiKeys();
}

function openCreation(): void {
  if (props.member || boolActionBlocked.value || !keyList.value) return;

  strSuccessMessage.value = "";
  boolCreating.value = true;
}

function openAction(apiKey: ApiKeyResponse, action: "edit" | "revoke"): void {
  if (
    boolActionBlocked.value ||
    (props.member && action === "edit") ||
    (action === "revoke" && getApiKeyStatus(apiKey, Date.now()) !== "active")
  )
    return;
  strSuccessMessage.value = "";
  selectedKey.value = { apiKey, action };
}

function applySavedKey(apiKey: ApiKeyResponse): void {
  const currentList = keyList.value;
  if (!currentList) return;

  const arrKey = [apiKey, ...currentList.api_keys.filter((key) => key.id !== apiKey.id)]
    .filter((key) => {
      const status = getApiKeyStatus(key, Date.now());
      const boolRetained =
        status === "active" ||
        (currentList.limits.inactive_retention_days > 0 &&
          currentList.limits.inactive_records > 0);
      return boolRetained && (!arrStatus.value.length || arrStatus.value.includes(status));
    })
    .sort(
      (first, second) =>
        Date.parse(second.created_at) - Date.parse(first.created_at) ||
        second.id.localeCompare(first.id),
    );
  keyList.value = { ...currentList, api_keys: arrKey };
  strUpdatedAt.value = null;
}

function handleCreated(apiKey: ApiKeyResponse): void {
  boolCreating.value = false;
  strSuccessMessage.value = `API key ${apiKey.name} created.`;
  applySavedKey(apiKey);
  void loadApiKeys();
}

function handleSaved(apiKey: ApiKeyResponse): void {
  const action = selectedKey.value?.action;
  selectedKey.value = null;
  strSuccessMessage.value =
    action === "revoke" ? `API key ${apiKey.name} revoked.` : "API key Notes updated.";
  applySavedKey(apiKey);
  void loadApiKeys();
}

function closeAndRefresh(): void {
  boolCreating.value = false;
  selectedKey.value = null;
  void loadApiKeys();
}

onMounted(() => void loadApiKeys());
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
