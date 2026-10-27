// FileName: navigation.ts

import type { Router, RouteLocationNormalized, RouteLocationRaw } from "vue-router";

import type {
  AccountAccessResponse,
  SessionUserResponse,
} from "../api/generated/browserApi";

export function getAuthenticatedRedirect(
  router: Router,
  route: Pick<RouteLocationNormalized, "name" | "meta" | "query">,
  user: SessionUserResponse,
  access: AccountAccessResponse | null,
): RouteLocationRaw | undefined {
  if (route.name === "sign-in" || route.name === "platform-sign-in") {
    const homeLocation = {
      name: user.is_platform_admin ? "platform-organizations" : "overview",
    };
    const returnTo = route.query.returnTo;
    if (
      typeof returnTo !== "string" ||
      !returnTo.startsWith("/") ||
      returnTo.startsWith("//") ||
      returnTo.length > 2048 ||
      returnTo.includes("\\") ||
      Array.from(returnTo).some((character) => character.charCodeAt(0) < 32)
    )
      return homeLocation;

    const returnRoute = router.resolve(returnTo);
    if (
      !returnRoute.matched.length ||
      returnRoute.meta.public ||
      Boolean(returnRoute.meta.requiresPlatformAdmin) !== user.is_platform_admin
    )
      return homeLocation;
    return returnRoute.fullPath;
  }

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
  router: Router,
  route: Pick<RouteLocationNormalized, "fullPath" | "meta">,
  platformAdmin = false,
): RouteLocationRaw {
  const boolPlatform = platformAdmin || route.meta.requiresPlatformAdmin === true;
  const strHomePath = router.resolve({
    name: boolPlatform ? "platform-organizations" : "overview",
  }).path;
  const strReturnPath =
    Boolean(route.meta.requiresPlatformAdmin) === boolPlatform
      ? route.fullPath
      : strHomePath;
  return {
    name: boolPlatform ? "platform-sign-in" : "sign-in",
    query: strReturnPath === strHomePath ? undefined : { returnTo: strReturnPath },
    replace: true,
  };
}
