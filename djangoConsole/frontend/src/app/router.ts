// FileName: router.ts

import { createRouter, createWebHistory } from "vue-router";
import type { Router, RouterHistory } from "vue-router";
import type { Pinia } from "pinia";

import { useSessionStore } from "../stores/session";

import { getSafeReturnPath, getSignInLocation } from "./navigation";

export function createAppRouter(
  pinia: Pinia,
  history: RouterHistory = createWebHistory(),
): Router {
  const router = createRouter({
    history,
    routes: [
      { path: "/", redirect: "/overview" },
      {
        path: "/sign-in",
        name: "sign-in",
        component: () => import("../views/SignInView.vue"),
        meta: { title: "Sign In", public: true },
      },
      {
        path: "/overview",
        name: "overview",
        component: () => import("../views/OverviewView.vue"),
        meta: { title: "Overview", requiresBusiness: true },
      },
      {
        path: "/my-profile",
        name: "my-profile",
        component: () => import("../views/ProfileView.vue"),
        meta: { title: "My Profile", requiresBusiness: true },
      },
      {
        path: "/help",
        name: "help",
        component: () => import("../views/HelpView.vue"),
        meta: { title: "Help & About" },
      },
      {
        path: "/organization-status",
        name: "organization-status",
        component: () => import("../views/OrganizationStatusView.vue"),
        meta: { title: "Organization Status" },
      },
      {
        path: "/:pathMatch(.*)*",
        name: "not-found",
        component: () => import("../views/NotFoundView.vue"),
        meta: { title: "Page Not Found", public: true },
      },
    ],
    scrollBehavior: () => ({ top: 0 }),
  });

  router.beforeEach(async (to) => {
    const sessionStore = useSessionStore(pinia);
    await sessionStore.initializeSession();
    if (sessionStore.status === "unavailable") return true;
    if (sessionStore.status === "anonymous" && !to.meta.public) {
      return getSignInLocation(to.fullPath);
    }
    if (sessionStore.authenticated) {
      if (to.name === "sign-in") return getSafeReturnPath(to.query.returnTo);
      if (to.meta.requiresBusiness && !sessionStore.access?.business_available)
        return { name: "organization-status" };
      if (to.name === "organization-status" && sessionStore.access?.business_available)
        return { name: "overview" };
    }
    return true;
  });
  return router;
}
