// FileName: navigation.ts

import type { RouteLocationRaw } from "vue-router";

const SET_RETURN_PATH = new Set([
  "/overview",
  "/packages",
  "/schedules",
  "/jobs",
  "/runs",
  "/organization-settings/run-email-recipients",
  "/executors",
  "/executors/groups",
  "/assets",
  "/data-queues",
  "/shared-files",
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
  /^\/(?:packages|schedules|jobs|runs|assets|data-queues|executors(?:\/groups)?|organization-settings\/(?:members|departments))\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function getSafeReturnPath(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048 || value.includes("\\"))
    return "/overview";
  if (Array.from(value).some((character) => character.charCodeAt(0) < 32))
    return "/overview";
  // Only application-owned workspace routes may be used after authentication.
  const strPath = value.split(/[?#]/, 1)[0];
  return strPath !== undefined &&
    (SET_RETURN_PATH.has(strPath) ||
      REGEXP_DETAILS_PATH.test(strPath) ||
      /^\/data-queues\/[0-9a-f-]{36}\/items\/[0-9a-f-]{36}$/i.test(strPath))
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
