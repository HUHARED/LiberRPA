// FileName: notifications.ts

import { requestApi } from "./client";
import {
  isRecord,
  isNonnegativeInteger,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import type {
  NotificationResponse,
  NotificationListResponse,
  NotificationDetailsRecordResponse,
  NotificationReadResponse,
} from "./generated/browserApi";

export type { NotificationResponse, NotificationDetailsRecordResponse };

function isNotificationResponse(value: unknown): value is NotificationResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    value.id.length > 0 &&
    typeof value.title === "string" &&
    isDateString(value.created_at) &&
    isNullableDateString(value.read_at)
  );
}

export async function getNotifications(): Promise<NotificationListResponse> {
  const response = await requestApi("/notifications/");
  if (
    !isRecord(response) ||
    !Array.isArray(response.notifications) ||
    !response.notifications.every(isNotificationResponse) ||
    !isNonnegativeInteger(response.unread_count) ||
    response.unread_count > response.notifications.length
  )
    return rejectInvalidResponse();
  return {
    notifications: response.notifications,
    unread_count: response.unread_count,
  };
}

export async function getNotificationDetails(
  id: string,
): Promise<NotificationDetailsRecordResponse> {
  const response = await requestApi(`/notifications/${encodeURIComponent(id)}/`);
  if (
    !isRecord(response) ||
    !isRecord(response.notification) ||
    !isNotificationResponse(response.notification) ||
    response.notification.id !== id ||
    typeof response.notification.detail !== "string"
  )
    return rejectInvalidResponse();
  return { ...response.notification, detail: response.notification.detail };
}

export async function markNotificationRead(id: string): Promise<NotificationReadResponse> {
  const response = await requestApi(`/notifications/${encodeURIComponent(id)}/read/`, {
    method: "POST",
    body: {},
  });
  if (!isRecord(response) || response.id !== id || !isDateString(response.read_at))
    return rejectInvalidResponse();
  return { id, read_at: response.read_at };
}

export async function markAllNotificationsRead(): Promise<void> {
  parseMessageResponse(
    await requestApi("/notifications/read-all/", { method: "POST", body: {} }),
  );
}

export async function deleteNotification(id: string): Promise<void> {
  parseMessageResponse(
    await requestApi(`/notifications/${encodeURIComponent(id)}/delete/`, {
      method: "POST",
      body: {},
    }),
  );
}

export async function clearNotifications(): Promise<void> {
  parseMessageResponse(
    await requestApi("/notifications/clear/", { method: "POST", body: {} }),
  );
}
