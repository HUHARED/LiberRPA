<!-- FileName: QueueDetailsView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
    <h1 class="text-h5">Queue Details{{ page ? ` — ${page.queue.name}` : "" }}</h1>
    <v-btn :to="{ name: 'data-queues', query: listQuery }" variant="text">
      Back to Queues
    </v-btn>
  </div>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
    {{ error.message
    }}<v-btn v-if="!page" variant="text" :disabled="boolLoading" @click="load">
      Retry
    </v-btn>
  </v-alert>
  <v-alert
    v-if="strActionError"
    type="error"
    variant="tonal"
    closable
    class="mb-4"
    role="alert"
    @click:close="strActionError = ''">
    {{ strActionError }}
  </v-alert>
  <v-alert v-if="strMessage" type="success" variant="tonal" class="mb-4" role="status">
    {{ strMessage }}
  </v-alert>
  <v-progress-linear v-if="boolLoading && !page" indeterminate />
  <template v-if="page">
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-text-field
          :model-value="page.queue.path"
          label="Path"
          variant="outlined"
          readonly
          hide-details />
        <v-textarea
          :model-value="page.queue.notes || '—'"
          label="Notes"
          variant="outlined"
          rows="2"
          readonly
          hide-details
          class="mt-4" />
        <p class="mt-4">
          Unclaimed: {{ page.queue.unclaimed_count }} · Claimed:
          {{ page.queue.claimed_count }}
        </p>
        <div class="d-flex flex-wrap ga-2 mt-4">
          <v-btn variant="tonal" @click="copyPath">Copy Path</v-btn>
          <v-btn
            v-if="page.queue.can_manage"
            variant="tonal"
            :disabled="boolBusy || !!error"
            @click="boolEditOpen = true">
            Edit Queue
          </v-btn>
          <v-btn
            v-if="page.queue.can_manage"
            color="error"
            variant="tonal"
            :disabled="boolBusy || !!error"
            @click="strConfirm = 'queue'">
            Delete Queue
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <form @submit.prevent="applyFilters">
          <v-row>
            <v-col cols="12" md="3">
              <v-select
                v-model="strStatus"
                :items="QUEUE_STATUSES"
                label="Status"
                variant="outlined"
                density="compact"
                hide-details
                :disabled="boolBusy" />
            </v-col>
            <v-col cols="12" md="5">
              <v-text-field
                v-model="strItemId"
                label="Item ID"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                :disabled="boolBusy" />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                v-model="strOrder"
                :items="QUEUE_ORDERS"
                label="Order"
                variant="outlined"
                density="compact"
                hide-details
                :disabled="boolBusy" />
            </v-col>
          </v-row>
          <div class="d-flex flex-wrap ga-2 mt-4">
            <v-btn type="submit" variant="tonal" color="primary" :disabled="boolBusy">
              Apply
            </v-btn>
            <v-btn variant="outlined" :disabled="boolBusy" @click="clearFilters">
              Clear Filters
            </v-btn>
          </div>
        </form>
      </v-card-text>
    </v-card>
    <div class="d-flex flex-wrap ga-2 mb-4">
      <v-btn
        color="primary"
        variant="tonal"
        :disabled="boolBusy || !!error"
        @click="boolUploadOpen = true">
        Upload Items
      </v-btn>
      <v-btn
        variant="tonal"
        :disabled="boolBusy || !!error || !boolCanReset"
        @click="strConfirm = 'reset'">
        Reset Selected
      </v-btn>
      <v-btn
        color="error"
        variant="tonal"
        :disabled="boolBusy || !!error || !selectedItemIds.length"
        @click="strConfirm = 'items'">
        Delete Selected
      </v-btn>
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolBusy"
        @click="load">
        Refresh
      </v-btn>
    </div>
    <p class="text-body-2 text-medium-emphasis mb-3">Time zone: {{ strTimeZone }}</p>
    <v-card variant="outlined">
      <v-data-table-server
        v-model="selectedItemIds"
        :headers="ARR_HEADER"
        :items="page.items"
        :items-length="page.total_count"
        :items-per-page="50"
        :page="page.page"
        :loading="boolLoading"
        :item-selectable="() => !boolBusy && !error"
        item-value="id"
        show-select
        select-strategy="page"
        disable-sort
        hide-default-footer
        :mobile-breakpoint="600">
        <template #item.data_summary="{ item }">
          <div class="table-text notes-summary">{{ item.data_summary }}</div>
        </template>
        <template #item.status="{ item }">
          {{ item.status === "claimed" ? "Claimed" : "Unclaimed" }}
        </template>
        <template #item.uploaded_by_name="{ item }">
          <div class="table-text-narrow">{{ item.uploaded_by_name }}</div>
        </template>
        <template #item.uploaded_at="{ item }">
          <span class="text-no-wrap">{{
            formatDateTime(item.uploaded_at, strTimeZone)
          }}</span>
        </template>
        <template #item.last_claimed_by_name="{ item }">
          <div class="table-text-narrow">
            {{ item.last_claimed_by_name || "—" }}
          </div>
        </template>
        <template #item.last_claimed_at="{ item }">
          <span class="text-no-wrap">
            {{ formatDateTime(item.last_claimed_at, strTimeZone) }}
          </span>
        </template>
        <template #item.actions="{ item }">
          <v-btn
            :to="{
              name: 'queue-item-details',
              params: { queueId, itemId: item.id },
              query: route.query,
            }"
            variant="text"
            size="small">
            View
          </v-btn>
        </template>
        <template #no-data>No items match the current filters.</template>
      </v-data-table-server>
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p>
          {{ page.total_count }} matching items · Page {{ page.page }} of
          {{ page.total_pages }}
        </p>
        <v-pagination
          v-if="page.total_pages > 1"
          :model-value="page.page"
          :length="page.total_pages"
          :total-visible="5"
          :disabled="boolBusy"
          @update:model-value="changePage" />
      </div>
    </v-card>
    <QueueFormDialog
      v-if="boolEditOpen"
      :queue="page.queue"
      @close="boolEditOpen = false"
      @saved="handleEdited" />
    <QueueUploadDialog
      v-if="boolUploadOpen"
      :queue="page.queue"
      @close="boolUploadOpen = false"
      @uploaded="handleUploaded" />
    <v-dialog
      :model-value="!!strConfirm"
      persistent
      max-width="560"
      aria-labelledby="queue-confirm-title">
      <v-card>
        <v-card-title id="queue-confirm-title">{{
          strConfirm === "reset"
            ? "Reset to Unclaimed"
            : strConfirm === "queue"
              ? "Delete Queue"
              : "Delete Items"
        }}</v-card-title>
        <v-card-text>
          <p class="text-break mb-3">{{ page.queue.path }}</p>
          <p>
            {{
              strConfirm === "queue"
                ? `Delete this queue and all ${page.queue.unclaimed_count + page.queue.claimed_count} items?`
                : strConfirm === "reset"
                  ? `Reset ${selectedItemIds.length} selected items to Unclaimed?`
                  : `Delete ${selectedItemIds.length} selected items?`
            }}
          </p>
          <v-alert
            v-if="mutationError"
            type="error"
            variant="tonal"
            class="mt-4"
            role="alert">
            The operation was not confirmed. {{ mutationError.message }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="boolSaving" @click="closeConfirm">Cancel</v-btn>
          <v-btn
            :color="strConfirm === 'reset' ? 'primary' : 'error'"
            variant="tonal"
            :disabled="boolSaving"
            :loading="boolSaving"
            @click="submitMutation">
            {{ strConfirm === "reset" ? "Reset" : "Delete" }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </template>
  <RouterView v-slot="{ Component }">
    <component :is="Component" :key="route.path" />
  </RouterView>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";

import QueueFormDialog from "@/components/dataQueues/QueueFormDialog.vue";
import QueueUploadDialog from "@/components/dataQueues/QueueUploadDialog.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import {
  QUEUE_STATUSES,
  QUEUE_ORDERS,
  getQueueItems,
  deleteQueue,
  changeQueueItems,
} from "@/api/dataQueues";
import type { QueueItemsResponse, QueueMutationResponse } from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ queueId: string }>();
const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const ARR_HEADER = [
  { title: "Data", key: "data_summary", minWidth: 220 },
  { title: "Status", key: "status" },
  { title: "Uploaded By", key: "uploaded_by_name", minWidth: 180 },
  { title: "Uploaded At", key: "uploaded_at", minWidth: 240 },
  { title: "Last Claimed By", key: "last_claimed_by_name", minWidth: 180 },
  { title: "Last Claimed At", key: "last_claimed_at", minWidth: 240 },
  { title: "Actions", key: "actions" },
];
const page = shallowRef<QueueItemsResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const mutationError = shallowRef<ApiError | null>(null);
const strMessage = ref("");
const strActionError = ref("");
const selectedItemIds = ref<string[]>([]);
const strStatus = ref("all");
const strOrder = ref("oldest_first");
const strItemId = ref<string | null>("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const boolEditOpen = ref(false);
const boolUploadOpen = ref(false);
const strConfirm = ref<"queue" | "items" | "reset" | null>(null);
const boolBusy = computed(() => boolLoading.value || boolSaving.value);
const boolCanReset = computed(() =>
  page.value?.items.some(
    (item) => selectedItemIds.value.includes(item.id) && item.status === "claimed",
  ),
);
const listQuery = computed(() => ({
  name: route.query.name,
  department_id: route.query.department_id,
  page: route.query.page,
}));
let intRevision = 0;
const getQueryText = (key: string, fallback: string): string =>
  typeof route.query[key] === "string" ? route.query[key] : fallback;
async function changePage(value: number): Promise<void> {
  selectedItemIds.value = [];
  await router.replace({ query: { ...route.query, item_page: String(value) } });
}

async function load(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  selectedItemIds.value = [];
  boolLoading.value = true;
  error.value = null;
  strActionError.value = "";
  try {
    const result = await getQueueItems(
      props.queueId,
      getQueryText("status", "all"),
      getQueryText("order", "oldest_first"),
      getQueryText("item_id", ""),
      Number(route.query.item_page) || 1,
    );
    if (intCurrentRevision === intRevision) {
      page.value = result;
      selectedItemIds.value = [];
    }
  } catch (e) {
    if (intCurrentRevision !== intRevision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.item_page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403, 404].includes(error.value.statusCode)) {
      page.value = null;
      boolEditOpen.value = false;
      boolUploadOpen.value = false;
      strConfirm.value = null;
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRevision) boolLoading.value = false;
  }
}
async function applyFilters(): Promise<void> {
  selectedItemIds.value = [];
  const query = {
    ...listQuery.value,
    status: strStatus.value,
    order: strOrder.value,
    item_id: strItemId.value?.trim() || undefined,
  };
  const location = {
    name: "data-queue-details",
    params: { queueId: props.queueId },
    query,
  };
  if (router.resolve(location).fullPath === route.fullPath) await load();
  else await router.replace(location);
}
function clearFilters(): void {
  strStatus.value = "all";
  strOrder.value = "oldest_first";
  strItemId.value = "";
  void applyFilters();
}
function handleEdited(): void {
  boolEditOpen.value = false;
  strMessage.value = "Queue updated.";
  void load();
}
function handleUploaded(result: QueueMutationResponse): void {
  boolUploadOpen.value = false;
  strMessage.value = `${result.item_ids.length} items uploaded${result.deduplicated ? " (original request confirmed)" : ""}.`;
  void load();
}
function closeConfirm(): void {
  strConfirm.value = null;
  mutationError.value = null;
}
async function submitMutation(): Promise<void> {
  if (boolSaving.value || !strConfirm.value || !sessionStore.session) return;
  const intCurrentRevision = intRevision;
  boolSaving.value = true;
  mutationError.value = null;
  try {
    if (strConfirm.value === "queue") {
      await deleteQueue(props.queueId);
      if (intCurrentRevision !== intRevision) return;
      await router.push({ name: "data-queues", query: listQuery.value });
      return;
    }
    const result = await changeQueueItems(
      sessionStore.session.user.id,
      props.queueId,
      strConfirm.value === "reset" ? "reset" : "delete_items",
      { item_ids: [...selectedItemIds.value] },
    );
    if (intCurrentRevision !== intRevision) return;
    strMessage.value = `${result.item_ids.length} items ${strConfirm.value === "reset" ? "reset" : "deleted"}; ${result.missing_ids.length} no longer present; ${result.skipped_ids.length} unchanged${result.deduplicated ? " (original request confirmed)" : ""}.`;
    closeConfirm();
    await load();
  } catch (e) {
    if (intCurrentRevision !== intRevision) return;
    mutationError.value = getApiError(e);
    if (mutationError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}
async function copyPath(): Promise<void> {
  if (!page.value) return;
  const intCurrentRevision = intRevision;
  strActionError.value = "";
  strMessage.value = "";
  try {
    await navigator.clipboard.writeText(page.value.queue.path);
    if (intCurrentRevision === intRevision) strMessage.value = "Path copied.";
  } catch {
    if (intCurrentRevision === intRevision)
      strActionError.value = "The path could not be copied. Copy it from the Path field.";
  }
}

watch(
  () => props.queueId,
  () => {
    page.value = null;
    strMessage.value = "";
  },
);
watch([strStatus, strOrder, strItemId], () => {
  selectedItemIds.value = [];
});
// Opening an item dialog must not reload the list or reset its selection and drafts.
watch(
  [
    () => props.queueId,
    () => getQueryText("status", "all"),
    () => getQueryText("order", "oldest_first"),
    () => getQueryText("item_id", ""),
    () => Number(route.query.item_page) || 1,
  ],
  () => {
    strStatus.value = getQueryText("status", "all");
    strOrder.value = getQueryText("order", "oldest_first");
    strItemId.value = getQueryText("item_id", "");
    closeConfirm();
    boolEditOpen.value = false;
    boolUploadOpen.value = false;
    void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  intRevision += 1;
});
</script>

<style scoped></style>
