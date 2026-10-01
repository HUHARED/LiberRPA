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
    }}<v-btn v-if="!page" variant="text" :disabled="loading" @click="load"> Retry </v-btn>
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
  <v-alert v-if="message" type="success" variant="tonal" class="mb-4" role="status">
    {{ message }}
  </v-alert>
  <v-progress-linear v-if="loading && !page" indeterminate />
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
            :disabled="busy || !!error"
            @click="editOpen = true">
            Edit Queue
          </v-btn>
          <v-btn
            v-if="page.queue.can_manage"
            color="error"
            variant="tonal"
            :disabled="busy || !!error"
            @click="confirm = 'queue'">
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
                v-model="status"
                :items="QUEUE_STATUSES"
                label="Status"
                variant="outlined"
                density="compact"
                hide-details
                :disabled="busy" />
            </v-col>
            <v-col cols="12" md="5">
              <v-text-field
                v-model="itemId"
                label="Item ID"
                variant="outlined"
                density="compact"
                hide-details
                clearable
                :disabled="busy" />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                v-model="order"
                :items="QUEUE_ORDERS"
                label="Order"
                variant="outlined"
                density="compact"
                hide-details
                :disabled="busy" />
            </v-col>
          </v-row>
          <div class="d-flex flex-wrap ga-2 mt-4">
            <v-btn type="submit" variant="tonal" color="primary" :disabled="busy">
              Apply
            </v-btn>
            <v-btn variant="outlined" :disabled="busy" @click="clearFilters">
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
        :disabled="busy || !!error"
        @click="uploadOpen = true">
        Upload Items
      </v-btn>
      <v-btn
        variant="tonal"
        :disabled="busy || !!error || !canReset"
        @click="confirm = 'reset'">
        Reset Selected
      </v-btn>
      <v-btn
        color="error"
        variant="tonal"
        :disabled="busy || !!error || !selected.length"
        @click="confirm = 'items'">
        Delete Selected
      </v-btn>
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="loading"
        :disabled="busy"
        @click="load">
        Refresh
      </v-btn>
    </div>
    <p class="text-body-2 text-medium-emphasis mb-3">Time zone: {{ timeZone }}</p>
    <v-card variant="outlined">
      <v-data-table-server
        v-model="selected"
        :headers="headers"
        :items="page.items"
        :items-length="page.total_count"
        :items-per-page="50"
        :page="page.page"
        :loading="loading"
        :item-selectable="() => !busy && !error"
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
          <span class="text-no-wrap">{{ formatDateTime(item.uploaded_at, timeZone) }}</span>
        </template>
        <template #item.last_claimed_by_name="{ item }">
          <div class="table-text-narrow">
            {{ item.last_claimed_by_name || "—" }}
          </div>
        </template>
        <template #item.last_claimed_at="{ item }">
          <span class="text-no-wrap">
            {{ formatDateTime(item.last_claimed_at, timeZone) }}
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
          :disabled="busy"
          @update:model-value="changePage" />
      </div>
    </v-card>
    <QueueFormDialog
      v-if="editOpen"
      :queue="page.queue"
      @close="editOpen = false"
      @saved="handleEdited" />
    <QueueUploadDialog
      v-if="uploadOpen"
      :queue="page.queue"
      @close="uploadOpen = false"
      @uploaded="handleUploaded" />
    <v-dialog
      :model-value="!!confirm"
      persistent
      max-width="560"
      aria-labelledby="queue-confirm-title">
      <v-card>
        <v-card-title id="queue-confirm-title">{{
          confirm === "reset"
            ? "Reset to Unclaimed"
            : confirm === "queue"
              ? "Delete Queue"
              : "Delete Items"
        }}</v-card-title>
        <v-card-text>
          <p class="text-break mb-3">{{ page.queue.path }}</p>
          <p>
            {{
              confirm === "queue"
                ? `Delete this queue and all ${page.queue.unclaimed_count + page.queue.claimed_count} items?`
                : confirm === "reset"
                  ? `Reset ${selected.length} selected items to Unclaimed?`
                  : `Delete ${selected.length} selected items?`
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
          <v-btn :disabled="saving" @click="closeConfirm">Cancel</v-btn>
          <v-btn
            :color="confirm === 'reset' ? 'primary' : 'error'"
            variant="tonal"
            :disabled="saving"
            :loading="saving"
            @click="submitMutation">
            {{ confirm === "reset" ? "Reset" : "Delete" }}
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
import type {
  QueueItemsResponse,
  QueueMutationResponse,
} from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ queueId: string }>();
const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const timeZone = computed(() => session.session?.user.time_zone ?? "UTC");
const headers = [
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
const message = ref("");
const strActionError = ref("");
const selected = ref<string[]>([]);
const status = ref("all");
const order = ref("oldest_first");
const itemId = ref<string | null>("");
const loading = ref(false);
const saving = ref(false);
const editOpen = ref(false);
const uploadOpen = ref(false);
const confirm = ref<"queue" | "items" | "reset" | null>(null);
const busy = computed(() => loading.value || saving.value);
const canReset = computed(() =>
  page.value?.items.some(
    (item) => selected.value.includes(item.id) && item.status === "claimed",
  ),
);
const listQuery = computed(() => ({
  name: route.query.name,
  department_id: route.query.department_id,
  page: route.query.page,
}));
let revision = 0;
const queryText = (key: string, fallback: string): string =>
  typeof route.query[key] === "string" ? route.query[key] : fallback;
async function changePage(value: number): Promise<void> {
  selected.value = [];
  await router.replace({ query: { ...route.query, item_page: String(value) } });
}

async function load(): Promise<void> {
  const current = ++revision;
  selected.value = [];
  loading.value = true;
  error.value = null;
  strActionError.value = "";
  try {
    const result = await getQueueItems(
      props.queueId,
      queryText("status", "all"),
      queryText("order", "oldest_first"),
      queryText("item_id", ""),
      Number(route.query.item_page) || 1,
    );
    if (current === revision) {
      page.value = result;
      selected.value = [];
    }
  } catch (e) {
    if (current !== revision) return;
    error.value = getApiError(e);
    if (error.value.code === "invalid_page" && Number(route.query.item_page) > 1) {
      await changePage(1);
      return;
    }
    if ([401, 403, 404].includes(error.value.statusCode)) {
      page.value = null;
      editOpen.value = false;
      uploadOpen.value = false;
      confirm.value = null;
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    if (current === revision) loading.value = false;
  }
}
async function applyFilters(): Promise<void> {
  selected.value = [];
  const query = {
    ...listQuery.value,
    status: status.value,
    order: order.value,
    item_id: itemId.value?.trim() || undefined,
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
  status.value = "all";
  order.value = "oldest_first";
  itemId.value = "";
  void applyFilters();
}
function handleEdited(): void {
  editOpen.value = false;
  message.value = "Queue updated.";
  void load();
}
function handleUploaded(result: QueueMutationResponse): void {
  uploadOpen.value = false;
  message.value = `${result.item_ids.length} items uploaded${result.deduplicated ? " (original request confirmed)" : ""}.`;
  void load();
}
function closeConfirm(): void {
  confirm.value = null;
  mutationError.value = null;
}
async function submitMutation(): Promise<void> {
  if (saving.value || !confirm.value || !session.session) return;
  const current = revision;
  saving.value = true;
  mutationError.value = null;
  try {
    if (confirm.value === "queue") {
      await deleteQueue(props.queueId);
      if (current !== revision) return;
      await router.push({ name: "data-queues", query: listQuery.value });
      return;
    }
    const result = await changeQueueItems(
      session.session.user.id,
      props.queueId,
      confirm.value === "reset" ? "reset" : "delete_items",
      { item_ids: [...selected.value] },
    );
    if (current !== revision) return;
    message.value = `${result.item_ids.length} items ${confirm.value === "reset" ? "reset" : "deleted"}; ${result.missing_ids.length} no longer present; ${result.skipped_ids.length} unchanged${result.deduplicated ? " (original request confirmed)" : ""}.`;
    closeConfirm();
    await load();
  } catch (e) {
    if (current !== revision) return;
    mutationError.value = getApiError(e);
    if (mutationError.value.statusCode === 403) await session.refreshSession();
  } finally {
    saving.value = false;
  }
}
async function copyPath(): Promise<void> {
  if (!page.value) return;
  const current = revision;
  strActionError.value = "";
  message.value = "";
  try {
    await navigator.clipboard.writeText(page.value.queue.path);
    if (current === revision) message.value = "Path copied.";
  } catch {
    if (current === revision)
      strActionError.value = "The path could not be copied. Copy it from the Path field.";
  }
}

watch(
  () => props.queueId,
  () => {
    page.value = null;
    message.value = "";
  },
);
watch([status, order, itemId], () => {
  selected.value = [];
});
// Opening an item dialog must not reload the list or reset its selection and drafts.
watch(
  [
    () => props.queueId,
    () => queryText("status", "all"),
    () => queryText("order", "oldest_first"),
    () => queryText("item_id", ""),
    () => Number(route.query.item_page) || 1,
  ],
  () => {
    status.value = queryText("status", "all");
    order.value = queryText("order", "oldest_first");
    itemId.value = queryText("item_id", "");
    closeConfirm();
    editOpen.value = false;
    uploadOpen.value = false;
    void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  revision += 1;
});
</script>

<style scoped></style>
