// FileName: navigation.ts

import type { RouteLocationNormalized, RouteLocationRaw } from "vue-router";

import type {
  AccountAccessResponse,
  SessionUserResponse,
} from "../api/generated/browserApi";

const SET_RETURN_PATH = new Set([
  "/overview",
  "/overview/analysis",
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
  "/organization-settings/usage-retention",
  "/organization-settings/audit-log",
  "/organization-settings/members",
  "/organization-settings/departments",
  "/my-profile",
  "/api-keys",
  "/help",
  "/organization-status",
]);
const REGEXP_DETAILS_PATH =
  /^\/(?:packages|schedules|jobs|runs|data-queues|executors(?:\/groups)?|organization-settings\/(?:members|departments))\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function getSafeReturnPath(value: unknown, platformAdmin = false): string {
  const strHomePath = platformAdmin ? "/platform/organizations" : "/overview";
  if (typeof value !== "string" || value.length > 2048 || value.includes("\\"))
    return strHomePath;
  if (Array.from(value).some((character) => character.charCodeAt(0) < 32))
    return strHomePath;

  const strPath = value.split(/[?#]/, 1)[0];
  if (strPath === undefined) return strHomePath;

  const boolPlatformPath =
    strPath === "/platform/organizations" ||
    strPath === "/platform/email" ||
    strPath === "/platform/audit-log" ||
    /^\/platform\/organizations\/[0-9a-f-]{36}(?:\/(?:limits|audit-log))?$/i.test(strPath);
  if (platformAdmin) return boolPlatformPath ? value : strHomePath;

  return SET_RETURN_PATH.has(strPath) ||
    REGEXP_DETAILS_PATH.test(strPath) ||
    /^\/data-queues\/[0-9a-f-]{36}\/items\/[0-9a-f-]{36}$/i.test(strPath)
    ? value
    : strHomePath;
}

export function getAuthenticatedRedirect(
  route: Pick<RouteLocationNormalized, "name" | "meta" | "query">,
  user: SessionUserResponse,
  access: AccountAccessResponse | null,
): RouteLocationRaw | undefined {
  if (route.name === "sign-in" || route.name === "platform-sign-in")
    return getSafeReturnPath(route.query.returnTo, user.is_platform_admin);

  if (user.is_platform_admin) {
    if (!route.meta.requiresPlatformAdmin && route.name !== "not-found")
      return { name: "platform-organizations" };
    return;
  }

  if (route.meta.requiresPlatformAdmin) return { name: "overview" };
  if (route.meta.requiresBusiness && !access?.business_available)
    return { name: "organization-status" };
  if (route.meta.requiresOrgAdmin && !access?.is_org_admin) return { name: "overview" };
  if (route.name === "organization-status" && access?.business_available)
    return { name: "overview" };
}

export function getSignInLocation(
  returnTo: unknown,
  platformAdmin = false,
): RouteLocationRaw {
  const boolPlatform =
    platformAdmin || (typeof returnTo === "string" && returnTo.startsWith("/platform/"));
  const strReturnPath = getSafeReturnPath(returnTo, boolPlatform);
  const strHomePath = boolPlatform ? "/platform/organizations" : "/overview";
  return {
    name: boolPlatform ? "platform-sign-in" : "sign-in",
    query: strReturnPath === strHomePath ? undefined : { returnTo: strReturnPath },
    replace: true,
  };
}
