<!-- FileName: NotificationsPanel.vue -->
<template>
  <v-menu
    v-model="boolOpen"
    :close-on-content-click="false"
    location="bottom end"
    max-width="480"
    @update:model-value="!$event && !details && closeDetails()">
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
            :disabled="boolBusy || intUnread === 0"
            @click="applyChange(markAllNotificationsRead)">
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
              @click.stop="applyChange(() => deleteNotification(notification.id))" />
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
        <v-alert v-if="strReadError" type="error" variant="tonal" class="mb-4">
          {{ strReadError }}
        </v-alert>

        <p class="text-pre-wrap text-break">{{ details.detail }}</p>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="closeDetails">Close</v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="boolClear" :persistent="boolBusy" max-width="520">
    <v-card ref="clearFeedbackContainer">
      <v-card-title>Clear All Notifications</v-card-title>

      <v-card-text>
        <p>Clear all your notifications?</p>

        <v-alert
          v-if="strClearError"
          ref="clearErrorAlert"
          type="error"
          variant="tonal"
          class="mt-4"
          role="alert"
          tabindex="-1">
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
          @click="applyChange(clearNotifications, true)">
          Clear All
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  getNotifications,
  getNotificationDetails,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
  clearNotifications,
} from "@/api/notifications";
import type {
  NotificationResponse,
  NotificationDetailsRecordResponse,
} from "@/api/notifications";
import { getApiError } from "@/api/errors";

import { useSessionStore } from "@/stores/sessionStore";

import { formatDateTime } from "@/app/formatters";
import { revealFormFeedback } from "@/app/formFeedback";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolAvailable = computed(
  () => !!sessionStore.session && sessionStore.access?.business_available === true,
);

const boolOpen = ref(false);
const boolClear = ref(false);
const boolActing = ref(false);
const boolDetailsLoading = ref(false);
const boolBusy = computed(() => boolActing.value || boolDetailsLoading.value);
const strError = ref("");
const strDetailsError = ref("");
const strReadError = ref("");
const strClearError = ref("");
const clearFeedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const clearErrorAlert = ref<{ $el: HTMLElement } | null>(null);
const intUnread = ref(0);
const arrNotification = ref<NotificationResponse[]>([]);
const details = ref<NotificationDetailsRecordResponse | null>(null);

let boolMounted = false;
let boolLoadRequested = false;
let intRevision = 0;
let intDetailsRequest = 0;
let loadTask: Promise<void> | null = null;

function load(): Promise<void> {
  if (!boolMounted || !boolAvailable.value) return Promise.resolve();
  boolLoadRequested = true;
  if (loadTask !== null) return loadTask;

  loadTask = (async () => {
    while (boolLoadRequested && boolMounted && boolAvailable.value) {
      boolLoadRequested = false;
      const intCurrentRevision = intRevision;
      try {
        const result = await getNotifications();
        if (!boolMounted || intCurrentRevision !== intRevision) continue;
        arrNotification.value = result.notifications;
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
  strReadError.value = "";
}

async function openDetails(id: string): Promise<void> {
  if (!boolMounted || !boolAvailable.value || boolActing.value || boolClear.value) return;
  const intCurrentRevision = intRevision;
  const intCurrentRequest = ++intDetailsRequest;
  const isCurrentRequest = (): boolean =>
    boolMounted &&
    intCurrentRevision === intRevision &&
    intCurrentRequest === intDetailsRequest;

  boolDetailsLoading.value = true;
  details.value = null;
  strDetailsError.value = "";
  strReadError.value = "";
  try {
    const notification = await getNotificationDetails(id);
    if (!isCurrentRequest()) return;
    details.value = notification;
    boolOpen.value = false;
    // Wait until Vue has rendered this accepted detail before marking it as read.
    await nextTick();
    if (!isCurrentRequest() || details.value?.id !== id || notification.read_at !== null)
      return;

    try {
      const result = await markNotificationRead(id);
      if (!boolMounted || intCurrentRevision !== intRevision) return;
      if (isCurrentRequest() && details.value?.id === id)
        details.value = { ...details.value, read_at: result.read_at };
      await load();
    } catch (e) {
      if (isCurrentRequest())
        strReadError.value = `Could not mark this notification as read. ${getApiError(e).message}`;
    }
  } catch (e) {
    if (isCurrentRequest()) strDetailsError.value = getApiError(e).message;
  } finally {
    if (isCurrentRequest()) boolDetailsLoading.value = false;
  }
}

function openClear(): void {
  if (boolBusy.value || !arrNotification.value.length) return;
  strClearError.value = "";
  boolClear.value = true;
}

async function applyChange(action: () => Promise<void>, clearAll = false): Promise<void> {
  if (!boolMounted || !boolAvailable.value || boolBusy.value) return;
  const intCurrentRevision = intRevision;
  boolActing.value = true;
  strError.value = "";
  strDetailsError.value = "";
  strClearError.value = "";
  try {
    await action();
    if (!boolMounted || intCurrentRevision !== intRevision) return;
    if (clearAll) boolClear.value = false;
    await load();
  } catch (e) {
    if (boolMounted && intCurrentRevision === intRevision) {
      if (clearAll) strClearError.value = getApiError(e).message;
      else strError.value = getApiError(e).message;
    }
  } finally {
    if (boolMounted && intCurrentRevision === intRevision) {
      boolActing.value = false;
      if (clearAll && boolClear.value && strClearError.value) {
        await nextTick();
        revealFormFeedback(clearFeedbackContainer.value?.$el, clearErrorAlert.value?.$el);
      }
    }
  }
}

function handleNotificationChange(): void {
  void load();
}

watch(
  [
    () => sessionStore.session?.user.id,
    () => sessionStore.access?.organization.id,
    () => boolAvailable.value,
  ],
  () => {
    intRevision += 1;
    closeDetails();
    boolLoadRequested = false;
    boolActing.value = false;
    arrNotification.value = [];
    intUnread.value = 0;
    boolOpen.value = false;
    boolClear.value = false;
    strError.value = "";
    strDetailsError.value = "";
    strClearError.value = "";
    if (boolAvailable.value) void load();
  },
  { flush: "sync" },
);

onMounted(() => {
  boolMounted = true;
  window.addEventListener("console-notifications-changed", handleNotificationChange);
  void load();
});

onBeforeUnmount(() => {
  boolMounted = false;
  boolLoadRequested = false;
  intRevision += 1;
  closeDetails();
  window.removeEventListener("console-notifications-changed", handleNotificationChange);
});
</script>

<style scoped></style>
