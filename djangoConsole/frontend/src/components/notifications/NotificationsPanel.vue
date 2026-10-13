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
        <v-alert v-if="strError" type="error" variant="tonal">{{ strError }}</v-alert>
        <div class="d-flex ga-2">
          <v-btn size="small" variant="tonal" :disabled="boolBusy" @click="act('read-all')">
            Mark All as Read
          </v-btn>
          <v-btn
            size="small"
            variant="tonal"
            :disabled="boolBusy || !arrNotification.length"
            @click="boolClear = true">
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
  <v-dialog :model-value="!!details" persistent max-width="700">
    <v-card v-if="details">
      <v-card-title>{{ details.title }}</v-card-title>
      <v-card-subtitle>
        {{ formatDateTime(details.created_at, strTimeZone) }}
      </v-card-subtitle>
      <v-card-text>
        <p class="text-pre-wrap text-break">{{ details.detail }}</p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" @click="details = null">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog v-model="boolClear" persistent max-width="520">
    <v-card>
      <v-card-title>Clear All Notifications</v-card-title>
      <v-card-text>Clear all your notifications?</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="boolClear = false">
          Cancel
        </v-btn>
        <v-btn variant="tonal" :loading="boolBusy" color="warning" @click="act('clear')">
          Clear All
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
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
const boolBusy = ref(false);
const strError = ref("");
const intUnread = ref(0);
const arrNotification = ref<NotificationInfo[]>([]);
const details = ref<(NotificationInfo & { detail: string }) | null>(null);
let timer: ReturnType<typeof setInterval> | undefined;
async function load(): Promise<void> {
  try {
    const result = await requestApi("/notifications/");
    if (
      !isRecord(result) ||
      !Array.isArray(result.notifications) ||
      typeof result.unread_count !== "number"
    )
      return rejectInvalidResponse();
    arrNotification.value = result.notifications as NotificationInfo[];
    intUnread.value = result.unread_count;
  } catch (e) {
    strError.value = getApiError(e).message;
  }
}
async function openDetails(id: string): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    const result = await requestApi(`/notifications/${encodeURIComponent(id)}/`);
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
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function act(action: string): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    await requestApi(`/notifications/${action}/`, { method: "POST", body: {} });
    boolClear.value = false;
    await load();
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
onMounted(() => {
  void load();
  timer = setInterval(() => {
    if (!document.hidden) void load();
  }, 30000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>
<style scoped></style>
