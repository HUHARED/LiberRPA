// FileName: router.ts

import { createRouter, createWebHistory } from "vue-router";
import type { Router, RouterHistory } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { getSafeReturnPath, getSignInLocation } from "./navigation";

export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({
    history,
    routes: [
      { path: "/", redirect: "/overview" },
      {
        path: "/create-organization",
        name: "create-organization",
        component: () => import("@/views/accounts/CreateOrganizationView.vue"),
        meta: { title: "Create Organization", public: true },
      },
      {
        path: "/confirm-email-change",
        name: "confirm-email-change",
        component: () => import("@/views/accounts/ConfirmEmailChangeView.vue"),
        meta: { title: "Confirm Email Change", public: true },
      },
      {
        path: "/create-account",
        name: "create-account",
        component: () => import("@/views/accounts/CreateAccountView.vue"),
        meta: { title: "Create Account", public: true },
      },
      {
        path: "/sign-in",
        name: "sign-in",
        component: () => import("@/views/accounts/SignInView.vue"),
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
        component: () => import("@/views/executors/ExecutorsView.vue"),
        meta: { title: "Executors", requiresBusiness: true },
      },
      {
        path: "/shared-files",
        name: "shared-files",
        component: () => import("@/views/sharedFiles/SharedFilesView.vue"),
        meta: { title: "Shared Files", requiresBusiness: true },
      },
      {
        path: "/data-queues",
        name: "data-queues",
        component: () => import("@/views/dataQueues/DataQueuesView.vue"),
        meta: { title: "Data Queues", requiresBusiness: true },
      },
      {
        path: "/data-queues/:queueId",
        name: "data-queue-details",
        component: () => import("@/views/dataQueues/QueueDetailsView.vue"),
        props: true,
        meta: { title: "Queue Details", requiresBusiness: true },
        children: [
          {
            path: "items/:itemId",
            name: "queue-item-details",
            component: () => import("@/components/dataQueues/QueueItemDetailsDialog.vue"),
            props: true,
            meta: { title: "Item Details" },
          },
        ],
      },
      {
        path: "/assets",
        name: "assets",
        component: () => import("@/views/assets/AssetsView.vue"),
        meta: { title: "Assets", requiresBusiness: true },
        children: [
          {
            path: ":assetId",
            name: "asset-details",
            component: () => import("@/components/assets/AssetDetailsDialog.vue"),
            props: true,
            meta: { title: "Asset Details" },
          },
        ],
      },
      {
        path: "/executors/groups",
        name: "executor-groups",
        component: () => import("@/views/executors/ExecutorGroupsView.vue"),
        meta: { title: "Executor Groups", requiresBusiness: true },
        children: [
          {
            path: ":groupId",
            name: "executor-group-details",
            component: () => import("@/components/executors/ExecutorGroupDetailsDialog.vue"),
            props: true,
            meta: { title: "Group Details" },
          },
        ],
      },
      {
        path: "/executors/:executorId",
        name: "executor-details",
        component: () => import("@/views/executors/ExecutorDetailsView.vue"),
        props: true,
        meta: { title: "Executor Details", requiresBusiness: true },
      },
      {
        path: "/organization-settings",
        name: "organization-settings",
        component: () => import("@/views/organizations/OrganizationSettingsView.vue"),
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
            component: () => import("@/views/organizations/OrganizationGeneralView.vue"),
            meta: { title: "General" },
          },
          {
            path: "audit-log",
            name: "audit-log",
            component: () => import("@/views/audit/AuditLogView.vue"),
            meta: { title: "Audit Log" },
          },
          {
            path: "members",
            name: "members",
            component: () => import("@/views/organizations/MembersView.vue"),
            meta: { title: "Members" },
          },
          {
            path: "members/:userId",
            name: "member-details",
            component: () => import("@/views/organizations/MemberDetailsView.vue"),
            props: true,
            meta: { title: "Member Details" },
          },
          {
            path: "departments",
            name: "departments",
            component: () => import("@/views/organizations/DepartmentsView.vue"),
            meta: { title: "Departments" },
          },
          {
            path: "departments/:departmentId",
            name: "department-details",
            component: () => import("@/views/organizations/DepartmentDetailsView.vue"),
            props: true,
            meta: { title: "Department Details" },
          },
        ],
      },
      {
        path: "/my-profile",
        name: "my-profile",
        component: () => import("@/views/accounts/ProfileView.vue"),
        meta: { title: "My Profile", requiresBusiness: true },
      },
      {
        path: "/api-keys",
        name: "api-keys",
        component: () => import("@/views/accounts/ApiKeysView.vue"),
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
        component: () => import("@/views/organizations/OrganizationStatusView.vue"),
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
      // Opening or closing a resource dialog keeps its mounted list and background position.
      if (
        ["executor-groups", "assets", "data-queue-details"].some(
          (name) =>
            to.matched.some((record) => record.name === name) &&
            from.matched.some((record) => record.name === name),
        )
      )
        return false;
      return savedPosition ?? { top: 0 };
    },
  });

  router.beforeEach(async (to, from) => {
    const sessionStore = useSessionStore();
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
