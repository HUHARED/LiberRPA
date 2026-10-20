<!-- FileName: ConsoleLayout.vue -->
<template>
  <a class="skip-link bg-surface text-primary pa-3 rounded" href="#main-content">
    Skip to content
  </a>
  <v-navigation-drawer
    v-model="boolDrawerOpen"
    :permanent="boolDesktop"
    :temporary="!boolDesktop"
    width="256">
    <template #prepend>
      <v-list-item class="py-4">
        <BrandMark />
      </v-list-item>
      <v-divider />
    </template>
    <v-list
      v-if="sessionStore.session?.user.is_platform_admin"
      tag="nav"
      nav
      density="compact"
      aria-label="Platform navigation">
      <v-list-subheader>Platform</v-list-subheader>
      <v-list-item
        title="Organizations"
        prepend-icon="mdi-office-building-cog-outline"
        to="/platform/organizations"
        :active="route.path.startsWith('/platform/organizations')"
        color="primary" />
      <v-list-item
        title="Service Settings"
        prepend-icon="mdi-cog-outline"
        to="/platform/service-settings"
        color="primary" />
      <v-list-item
        title="Instance Status"
        prepend-icon="mdi-server-outline"
        to="/platform/instance-status"
        :active="route.path.startsWith('/platform/instance-status')"
        color="primary" />
      <v-list-item
        title="Maintenance"
        prepend-icon="mdi-wrench-outline"
        to="/platform/maintenance"
        color="primary" />
      <v-list-item
        title="Platform Audit Log"
        prepend-icon="mdi-history"
        to="/platform/audit-log"
        color="primary" />
    </v-list>

    <v-list
      v-if="!sessionStore.session?.user.is_platform_admin && sessionStore.access"
      tag="nav"
      nav
      density="compact"
      aria-label="Workspace navigation">
      <v-list-subheader>Workspace</v-list-subheader>
      <v-list-item
        v-for="navigationItem in arrNavigation"
        :key="navigationItem.title"
        :title="navigationItem.title"
        :prepend-icon="navigationItem.icon"
        :to="'path' in navigationItem ? navigationItem.path : undefined"
        :active="
          'path' in navigationItem && route.path.startsWith(`${navigationItem.path}/`)
            ? true
            : undefined
        "
        :disabled="!('path' in navigationItem) || !sessionStore.access?.business_available"
        :aria-label="navigationItem.title"
        color="primary" />
    </v-list>
  </v-navigation-drawer>
  <v-app-bar flat border="b" height="64">
    <v-btn
      v-if="!boolDesktop"
      icon="mdi-menu"
      aria-label="Open navigation"
      @click="boolDrawerOpen = true" />
    <v-app-bar-title class="text-body-1">
      <v-icon
        :icon="
          sessionStore.session?.user.is_platform_admin
            ? 'mdi-office-building-cog-outline'
            : 'mdi-office-building-outline'
        "
        class="mr-2" />
      {{
        sessionStore.session?.user.is_platform_admin
          ? "Platform"
          : (sessionStore.access?.organization.name ?? "LiberRPA Console")
      }}
    </v-app-bar-title>
    <template #append>
      <NotificationsPanel v-if="!sessionStore.session?.user.is_platform_admin" />
      <v-menu location="bottom end">
        <template #activator="{ props }">
          <v-btn variant="text" v-bind="props" class="mr-2" aria-label="Open account menu">
            <v-avatar color="primary" variant="tonal" size="32" class="mr-2">
              {{ strAvatarInitial }}
            </v-avatar>
            <span class="d-none d-md-inline">{{ strDisplayName }}</span>
            <v-icon icon="mdi-chevron-down" class="ml-1" />
          </v-btn>
        </template>
        <v-list min-width="248" density="compact">
          <v-list-item
            :title="strDisplayName"
            :subtitle="
              sessionStore.session?.user.is_platform_admin
                ? 'Platform Administrator'
                : sessionStore.session?.user.email
            " />
          <v-divider class="my-2" />
          <v-list-item
            v-if="
              !sessionStore.session?.user.is_platform_admin &&
              sessionStore.access?.business_available
            "
            to="/my-profile"
            title="My Profile"
            prepend-icon="mdi-account-circle-outline" />
          <v-list-item
            v-if="
              !sessionStore.session?.user.is_platform_admin &&
              sessionStore.access?.business_available
            "
            to="/api-keys"
            title="API Keys"
            prepend-icon="mdi-key-outline" />
          <v-list-item
            v-if="!sessionStore.session?.user.is_platform_admin"
            to="/help"
            title="Help & About"
            prepend-icon="mdi-help-circle-outline" />
          <v-divider class="my-2" />
          <v-list-subheader>Appearance</v-list-subheader>
          <v-list-item
            v-for="themeOption in ARR_THEME_OPTION"
            :key="themeOption.value"
            :title="themeOption.title"
            :append-icon="
              preferencesStore.theme === themeOption.value ? 'mdi-check' : undefined
            "
            @click="preferencesStore.setTheme(themeOption.value)" />
          <v-divider class="my-2" />
          <v-list-item
            title="Sign Out"
            prepend-icon="mdi-logout"
            :disabled="sessionStore.busy"
            @click="submitSignOut" />
        </v-list>
      </v-menu>
    </template>
  </v-app-bar>
  <v-main id="main-content" tabindex="-1">
    <v-container fluid class="pa-4 pa-md-6">
      <v-alert
        v-if="signOutError"
        type="error"
        variant="tonal"
        closable
        class="mb-4"
        role="alert"
        @click:close="signOutError = null">
        Sign out was not confirmed. {{ signOutError.message }}
      </v-alert>
      <slot />
    </v-container>
  </v-main>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";

import NotificationsPanel from "@/components/notifications/NotificationsPanel.vue";
import BrandMark from "@/components/common/BrandMark.vue";

import { useSessionStore } from "../stores/sessionStore";
import { usePreferencesStore } from "../stores/preferencesStore";

import { type ApiError, getApiError } from "../api/errors";
import { getDisplayName } from "../app/formatters";

const ARR_NAVIGATION = [
  { title: "Overview", icon: "mdi-chart-box-outline", path: "/overview" },
  { title: "Packages", icon: "mdi-package-variant-closed", path: "/packages" },
  { title: "Executors", icon: "mdi-monitor", path: "/executors" },
  { title: "Schedules", icon: "mdi-calendar-clock-outline", path: "/schedules" },
  { title: "Job Queue", icon: "mdi-queue-first-in-last-out", path: "/jobs" },
  { title: "Run History", icon: "mdi-clipboard-text-clock-outline", path: "/runs" },
  { title: "Assets", icon: "mdi-archive-outline", path: "/assets" },
  { title: "Data Queues", icon: "mdi-database-outline", path: "/data-queues" },
  { title: "Shared Files", icon: "mdi-folder-outline", path: "/shared-files" },
  {
    title: "Organization Settings",
    icon: "mdi-cog-outline",
    path: "/organization-settings",
    requiresOrgAdmin: true,
  },
] as const;
const ARR_THEME_OPTION = [
  { title: "Use system theme", value: "system" },
  { title: "Light theme", value: "light" },
  { title: "Dark theme", value: "dark" },
] as const;

const sessionStore = useSessionStore();
const arrNavigation = computed(() =>
  ARR_NAVIGATION.filter(
    (navigationItem) =>
      !("requiresOrgAdmin" in navigationItem) || sessionStore.access?.is_org_admin,
  ),
);
const preferencesStore = usePreferencesStore();
const route = useRoute();
const display = useDisplay();
const boolDesktop = computed(() => display.mdAndUp.value);
const boolDrawerOpen = ref(boolDesktop.value);
const signOutError = shallowRef<ApiError | null>(null);
const strDisplayName = computed(() =>
  sessionStore.session?.user.is_platform_admin
    ? sessionStore.session.user.platform_login
    : getDisplayName(
        sessionStore.session?.user.username ?? "",
        sessionStore.session?.user.email ?? "",
      ),
);
const strAvatarInitial = computed(
  () => Array.from(strDisplayName.value.trim())[0]?.toLocaleUpperCase() ?? "?",
);
watch(boolDesktop, (desktop) => {
  boolDrawerOpen.value = desktop;
});
watch(
  () => route.fullPath,
  () => {
    if (!boolDesktop.value) boolDrawerOpen.value = false;
  },
);

async function submitSignOut(): Promise<void> {
  signOutError.value = null;
  try {
    await sessionStore.signOutAccount();
  } catch (e) {
    signOutError.value = getApiError(e);
  }
}
</script>

<style scoped></style>
