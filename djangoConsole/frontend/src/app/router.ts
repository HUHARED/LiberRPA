// FileName: router.ts

import { createRouter, createWebHistory } from "vue-router";
import type { Router, RouterHistory } from "vue-router";
import type { Pinia } from "pinia";

import { useSessionStore } from "../stores/sessionStore";

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
        path: "/confirm-email-change",
        name: "confirm-email-change",
        component: () => import("../views/ConfirmEmailChangeView.vue"),
        meta: { title: "Confirm Email Change", public: true },
      },
      {
        path: "/create-account",
        name: "create-account",
        component: () => import("../views/CreateAccountView.vue"),
        meta: { title: "Create Account", public: true },
      },
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
        path: "/executors",
        name: "executors",
        component: () => import("../views/ExecutorsView.vue"),
        meta: { title: "Executors", requiresBusiness: true },
      },
      {
        path: "/executors/groups",
        name: "executor-groups",
        component: () => import("../views/ExecutorGroupsView.vue"),
        meta: { title: "Executor Groups", requiresBusiness: true },
        children: [
          {
            path: ":groupId",
            name: "executor-group-details",
            component: () => import("../components/ExecutorGroupDetailsDialog.vue"),
            props: true,
            meta: { title: "Group Details" },
          },
        ],
      },
      {
        path: "/executors/:executorId",
        name: "executor-details",
        component: () => import("../views/ExecutorDetailsView.vue"),
        props: true,
        meta: { title: "Executor Details", requiresBusiness: true },
      },
      {
        path: "/organization-settings",
        name: "organization-settings",
        component: () => import("../views/OrganizationSettingsView.vue"),
        redirect: { name: "organization-general" },
        meta: {
          title: "Organization Settings",
          requiresBusiness: true,
          requiresOrgAdmin: true,
        },
        children: [
          {
            path: "general",
            name: "organization-general",
            component: () => import("../views/OrganizationGeneralView.vue"),
            meta: { title: "General" },
          },
          {
            path: "audit-log",
            name: "audit-log",
            component: () => import("../views/AuditLogView.vue"),
            meta: { title: "Audit Log" },
          },
          {
            path: "members",
            name: "members",
            component: () => import("../views/MembersView.vue"),
            meta: { title: "Members" },
          },
          {
            path: "members/:userId",
            name: "member-details",
            component: () => import("../views/MemberDetailsView.vue"),
            props: true,
            meta: { title: "Member Details" },
          },
          {
            path: "departments",
            name: "departments",
            component: () => import("../views/DepartmentsView.vue"),
            meta: { title: "Departments" },
          },
          {
            path: "departments/:departmentId",
            name: "department-details",
            component: () => import("../views/DepartmentDetailsView.vue"),
            props: true,
            meta: { title: "Department Details" },
          },
        ],
      },
      {
        path: "/my-profile",
        name: "my-profile",
        component: () => import("../views/ProfileView.vue"),
        meta: { title: "My Profile", requiresBusiness: true },
      },
      {
        path: "/api-keys",
        name: "api-keys",
        component: () => import("../views/ApiKeysView.vue"),
        meta: { title: "API Keys", requiresBusiness: true },
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
    scrollBehavior: (to, from, savedPosition) => {
      // Opening or closing a group dialog keeps its mounted list and background position.
      if (
        to.matched.some((record) => record.name === "executor-groups") &&
        from.matched.some((record) => record.name === "executor-groups")
      )
        return false;
      return savedPosition ?? { top: 0 };
    },
  });

  router.beforeEach(async (to, from) => {
    const sessionStore = useSessionStore(pinia);
    await sessionStore.initializeSession();
    // Keep an open page mounted until the session can be checked again.
    if (sessionStore.unavailable) return from.matched.length === 0;
    if (sessionStore.status === "anonymous" && !to.meta.public) {
      return getSignInLocation(to.fullPath);
    }
    if (sessionStore.authenticated) {
      if (to.name === "sign-in") return getSafeReturnPath(to.query.returnTo);
      if (to.meta.requiresBusiness && !sessionStore.access?.business_available)
        return { name: "organization-status" };
      if (to.meta.requiresOrgAdmin && !sessionStore.access?.is_org_admin)
        return { name: "overview" };
      if (to.name === "organization-status" && sessionStore.access?.business_available)
        return { name: "overview" };
    }
    return true;
  });
  return router;
}
