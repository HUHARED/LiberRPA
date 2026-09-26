// FileName: navigation.ts

import type { RouteLocationRaw } from "vue-router";

const SET_RETURN_PATH = new Set([
  "/overview",
  "/executors",
  "/my-profile",
  "/help",
  "/organization-status",
]);

export function getSafeReturnPath(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048 || value.includes("\\"))
    return "/overview";
  if (Array.from(value).some((character) => character.charCodeAt(0) < 32))
    return "/overview";
  // Only application-owned workspace routes may be used after authentication.
  const strPath = value.split(/[?#]/, 1)[0];
  return strPath !== undefined && SET_RETURN_PATH.has(strPath) ? value : "/overview";
}

export function getSignInLocation(returnTo: unknown): RouteLocationRaw {
  const strReturnPath = getSafeReturnPath(returnTo);
  return {
    name: "sign-in",
    query: strReturnPath === "/overview" ? undefined : { returnTo: strReturnPath },
    replace: true,
  };
}

export function getDisplayName(username: string, email: string): string {
  return username || email;
}

export function getAvatarInitial(username: string, email: string): string {
  return Array.from(getDisplayName(username, email).trim())[0]?.toLocaleUpperCase() ?? "?";
}

export function formatDateTime(value: string | null, timeZone?: string): string {
  if (value === null) return "—";
  const dateValue = new Date(value);
  if (!Number.isFinite(dateValue.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "long",
    timeZone,
  }).format(dateValue);
}
