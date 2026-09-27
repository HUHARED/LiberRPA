// FileName: navigation.ts

import type { RouteLocationRaw } from "vue-router";

const SET_RETURN_PATH = new Set([
  "/overview",
  "/executors",
  "/executors/groups",
  "/organization-settings",
  "/organization-settings/general",
  "/organization-settings/audit-log",
  "/organization-settings/members",
  "/organization-settings/departments",
  "/my-profile",
  "/api-keys",
  "/help",
  "/organization-status",
]);
const REGEXP_DETAILS_PATH =
  /^\/(?:executors(?:\/groups)?|organization-settings\/(?:members|departments))\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function getSafeReturnPath(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048 || value.includes("\\"))
    return "/overview";
  if (Array.from(value).some((character) => character.charCodeAt(0) < 32))
    return "/overview";
  // Only application-owned workspace routes may be used after authentication.
  const strPath = value.split(/[?#]/, 1)[0];
  return strPath !== undefined &&
    (SET_RETURN_PATH.has(strPath) || REGEXP_DETAILS_PATH.test(strPath))
    ? value
    : "/overview";
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

export function formatDateTime(value: string | null, timeZone: string): string {
  if (value === null) return "—";
  const dateValue = new Date(value);
  if (!Number.isFinite(dateValue.getTime())) return "Unknown";
  const arrPart = new Intl.DateTimeFormat("en", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "longOffset",
  }).formatToParts(dateValue);
  const mapPart = new Map(arrPart.map((part) => [part.type, part.value]));
  // Intl uses "GMT" for a zero offset and "GMT±HH:mm" for other offsets.
  const strOffset = mapPart.get("timeZoneName")?.replace("GMT", "") || "+00:00";
  const strDate = `${mapPart.get("year")}-${mapPart.get("month")}-${mapPart.get("day")}`;
  const strTime = `${mapPart.get("hour")}:${mapPart.get("minute")}:${mapPart.get("second")}`;
  return `${strDate} ${strTime} ${strOffset}`;
}

export function formatDateTimeInput(value: string, timeZone: string): string {
  const arrPart = new Intl.DateTimeFormat("en", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const mapPart = new Map(arrPart.map((part) => [part.type, part.value]));
  return `${mapPart.get("year")}-${mapPart.get("month")}-${mapPart.get("day")}T${mapPart.get("hour")}:${mapPart.get("minute")}`;
}
