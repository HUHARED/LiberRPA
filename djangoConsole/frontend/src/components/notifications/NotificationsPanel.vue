<!-- FileName: NotificationsPanel.vue -->
<template>
  <v-menu
    v-model="boolOpen"
    :close-on-content-click="false"
    location="bottom end"
    max-width="480">
    <template #activator="{ props: menuProps }">
      <v-btn v-bind="menuProps" icon aria-label="Notifications" @click="load">
        <v-badge :content="intUnread" :model-value="intUnread > 0" color="error">
          <v-icon icon="mdi-bell-outline" />
        </v-badge>
      </v-btn>
    </template>

    <v-card min-width="360">
      <v-card-title>Notifications</v-card-title>

      <v-card-text>
        <v-alert v-if="strDetailsError || strError" type="error" variant="tonal">
          {{ strDetailsError || strError }}
        </v-alert>

        <div class="d-flex justify-end ga-2">
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-email-open-outline"
            :disabled="boolBusy"
            @click="act('read-all')">
            Mark All as Read
          </v-btn>

          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-delete-outline"
            :disabled="boolBusy || !arrNotification.length"
            @click="openClear">
            Clear All
          </v-btn>
        </div>
      </v-card-text>

      <v-list max-height="480" lines="two">
        <v-list-item
          v-for="notification in arrNotification"
          :key="notification.id"
          :title="notification.title"
          :subtitle="formatDateTime(notification.created_at, strTimeZone)"
          :prepend-icon="notification.read_at ? 'mdi-email-open-outline' : 'mdi-email'"
          @click="openDetails(notification.id)">
          <template #append>
            <v-btn
              icon="mdi-delete-outline"
              size="small"
              variant="text"
              :disabled="boolBusy"
              aria-label="Delete notification"
              @click.stop="act(`${notification.id}/delete`)" />
          </template>
        </v-list-item>

        <v-list-item v-if="!arrNotification.length" title="No notifications." />
      </v-list>
    </v-card>
  </v-menu>

  <v-dialog
    :model-value="!!details"
    max-width="700"
    @update:model-value="!$event && closeDetails()">
    <v-card v-if="details">
      <v-card-title>{{ details.title }}</v-card-title>

      <v-card-subtitle>
        {{ formatDateTime(details.created_at, strTimeZone) }}
      </v-card-subtitle>

      <v-card-text>
        <p class="text-pre-wrap text-break">{{ details.detail }}</p>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="closeDetails">Close</v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="boolClear" :persistent="boolBusy" max-width="520">
    <v-card>
      <v-card-title>Clear All Notifications</v-card-title>

      <v-card-text>
        <p>Clear all your notifications?</p>

        <v-alert v-if="strClearError" type="error" variant="tonal" class="mt-4">
          {{ strClearError }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="boolClear = false">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :loading="boolBusy"
          color="warning"
          @click="act('clear')">
          Clear All
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { requestApi } from "@/api/client";
import { isRecord, rejectInvalidResponse } from "@/api/responses";
import { getApiError } from "@/api/errors";

import { useSessionStore } from "@/stores/sessionStore";

import { formatDateTime } from "@/app/formatters";

interface NotificationInfo {
  id: string;
  title: string;
  created_at: string;
  read_at: string | null;
}

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolOpen = ref(false);
const boolClear = ref(false);
const boolActing = ref(false);
const boolDetailsLoading = ref(false);
const boolBusy = computed(() => boolActing.value || boolDetailsLoading.value);
const strError = ref("");
const strDetailsError = ref("");
const strClearError = ref("");
const intUnread = ref(0);
const arrNotification = ref<NotificationInfo[]>([]);
const details = ref<(NotificationInfo & { detail: string }) | null>(null);
let boolMounted = false;
let boolLoadRequested = false;
let intRevision = 0;
let intDetailsRequest = 0;
let loadTask: Promise<void> | null = null;

function load(): Promise<void> {
  if (!boolMounted || !sessionStore.access?.business_available) return Promise.resolve();
  boolLoadRequested = true;
  if (loadTask !== null) return loadTask;

  loadTask = (async () => {
    while (boolLoadRequested && boolMounted && sessionStore.access?.business_available) {
      boolLoadRequested = false;
      const intCurrentRevision = intRevision;
      try {
        const result = await requestApi("/notifications/");
        if (!boolMounted || intCurrentRevision !== intRevision) continue;
        if (
          !isRecord(result) ||
          !Array.isArray(result.notifications) ||
          typeof result.unread_count !== "number"
        )
          return rejectInvalidResponse();
        arrNotification.value = result.notifications as NotificationInfo[];
        intUnread.value = result.unread_count;
        strError.value = "";
      } catch (e) {
        if (boolMounted && intCurrentRevision === intRevision)
          strError.value = getApiError(e).message;
      }
    }
  })().finally(() => {
    loadTask = null;
  });
  return loadTask;
}

function closeDetails(): void {
  intDetailsRequest += 1;
  details.value = null;
  boolDetailsLoading.value = false;
}

async function openDetails(id: string): Promise<void> {
  const intCurrentRevision = intRevision;
  const intCurrentRequest = ++intDetailsRequest;
  boolDetailsLoading.value = true;
  strDetailsError.value = "";
  try {
    const result = await requestApi(`/notifications/${encodeURIComponent(id)}/`);
    if (
      !boolMounted ||
      intCurrentRevision !== intRevision ||
      intCurrentRequest !== intDetailsRequest
    )
      return;
    if (
      !isRecord(result) ||
      !isRecord(result.notification) ||
      typeof result.notification.detail !== "string"
    )
      return rejectInvalidResponse();
    details.value = result.notification as unknown as NotificationInfo & { detail: string };
    boolOpen.value = false;
    await load();
  } catch (e) {
    if (
      boolMounted &&
      intCurrentRevision === intRevision &&
      intCurrentRequest === intDetailsRequest
    )
      strDetailsError.value = getApiError(e).message;
  } finally {
    if (
      boolMounted &&
      intCurrentRevision === intRevision &&
      intCurrentRequest === intDetailsRequest
    )
      boolDetailsLoading.value = false;
  }
}

function openClear(): void {
  strClearError.value = "";
  boolClear.value = true;
}

async function act(action: string): Promise<void> {
  if (boolBusy.value) return;
  const intCurrentRevision = intRevision;
  boolActing.value = true;
  strError.value = "";
  strDetailsError.value = "";
  strClearError.value = "";
  try {
    await requestApi(`/notifications/${action}/`, { method: "POST", body: {} });
    if (!boolMounted || intCurrentRevision !== intRevision) return;
    boolClear.value = false;
    await load();
  } catch (e) {
    if (boolMounted && intCurrentRevision === intRevision) {
      if (action === "clear") strClearError.value = getApiError(e).message;
      else strError.value = getApiError(e).message;
    }
  } finally {
    if (boolMounted && intCurrentRevision === intRevision) boolActing.value = false;
  }
}

function handleNotificationChange(): void {
  void load();
}

watch(
  () => sessionStore.access?.business_available,
  (boolAvailable) => {
    intRevision += 1;
    closeDetails();
    boolActing.value = false;
    if (boolAvailable) {
      void load();
    } else {
      boolLoadRequested = false;
      arrNotification.value = [];
      intUnread.value = 0;
      boolOpen.value = false;
      boolClear.value = false;
      strError.value = "";
      strDetailsError.value = "";
      strClearError.value = "";
    }
  },
);

onMounted(() => {
  boolMounted = true;
  window.addEventListener("console-notifications-changed", handleNotificationChange);
  void load();
});

onBeforeUnmount(() => {
  boolMounted = false;
  intRevision += 1;
  window.removeEventListener("console-notifications-changed", handleNotificationChange);
});
</script>

<style scoped></style>
