// FileName: notifications.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  rejectInvalidResponse,
  parseMessageResponse,
} from "./responses";

import type {
  NotificationResponse,
  NotificationListResponse,
  NotificationDetailsResponse,
  NotificationDetailsRecordResponse,
  NotificationReadResponse,
} from "./generated/browserApi";

export type { NotificationResponse, NotificationDetailsRecordResponse };

export async function getNotifications(): Promise<NotificationListResponse> {
  return requestApi<NotificationListResponse>("/notifications/");
}

export async function getNotificationDetails(
  id: string,
): Promise<NotificationDetailsRecordResponse> {
  const response = await requestApi<NotificationDetailsResponse>(
    `/notifications/${encodeURIComponent(id)}/`,
  );
  if (
    !isRecord(response) ||
    !isRecord(response.notification) ||
    response.notification.id !== id ||
    !isNullableDateString(response.notification.read_at) ||
    typeof response.notification.detail !== "string"
  )
    return rejectInvalidResponse();
  return response.notification;
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
