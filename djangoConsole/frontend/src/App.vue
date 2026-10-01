<!-- FileName: App.vue -->
<template>
  <v-app>
    <AuthLayout v-if="sessionStore.status === 'unknown'">
      <ConnectionState
        :loading="!sessionStore.unavailable"
        :message="sessionStore.issue?.message"
        :retrying="boolRetrying"
        @retry="retryConnection" />
    </AuthLayout>

    <div
      v-else-if="sessionStore.authenticated || route.meta.public"
      :key="sessionStore.authenticated ? sessionStore.session?.user.id : 'anonymous'"
      :inert="sessionStore.unavailable"
      class="d-flex flex-column flex-grow-1">
      <ConsoleLayout v-if="sessionStore.authenticated && !route.meta.public">
        <RouterView />
      </ConsoleLayout>
      <RouterView v-else />
    </div>

    <v-dialog
      :model-value="sessionStore.unavailable && sessionStore.status !== 'unknown'"
      persistent
      no-click-animation
      max-width="480"
      aria-label="Unable to connect">
      <v-card>
        <v-card-text class="pa-6">
          <ConnectionState
            :message="sessionStore.issue?.message"
            :retrying="boolRetrying"
            @retry="retryConnection" />
        </v-card-text>
      </v-card>
    </v-dialog>
    <v-footer
      app
      border="t"
      class="flex-column flex-sm-row justify-center ga-2 text-body-2 text-medium-emphasis">
      <span>© 2025–{{ intCurrentYear }} Jiyan Hu</span>
      <span class="d-none d-sm-inline" aria-hidden="true">|</span>
      <span>2 + 2 = 4</span>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useTheme } from "vuetify";

import { useSessionStore } from "./stores/sessionStore";
import { usePreferencesStore } from "./stores/preferencesStore";
import { useSessionLifecycle } from "./composables/useSessionLifecycle";

import { getSafeReturnPath, getSignInLocation } from "./app/navigation";

import ConnectionState from "./components/ConnectionState.vue";
import AuthLayout from "./layouts/AuthLayout.vue";
import ConsoleLayout from "./layouts/ConsoleLayout.vue";

const sessionStore = useSessionStore();
const preferencesStore = usePreferencesStore();
const router = useRouter();
const route = useRoute();
const theme = useTheme();
const intCurrentYear = new Date().getFullYear();
const boolRetrying = ref(false);
useSessionLifecycle();

watch(() => preferencesStore.theme, theme.change, { immediate: true });

watch(
  [
    () => sessionStore.status,
    () => sessionStore.access,
    () => sessionStore.unavailable,
    () => route.fullPath,
  ],
  () => {
    if (sessionStore.unavailable) return;

    if (sessionStore.status === "anonymous" && route.matched.length && !route.meta.public) {
      void router.replace(getSignInLocation(route.fullPath));
    } else if (sessionStore.authenticated) {
      if (route.name === "sign-in")
        void router.replace(getSafeReturnPath(route.query.returnTo));
      else if (route.meta.requiresBusiness && !sessionStore.access?.business_available) {
        void router.replace({ name: "organization-status" });
      } else if (route.meta.requiresOrgAdmin && !sessionStore.access?.is_org_admin) {
        void router.replace({ name: "overview" });
      } else if (
        route.name === "organization-status" &&
        sessionStore.access?.business_available
      ) {
        void router.replace({ name: "overview" });
      }
    }
  },
);

async function retryConnection(): Promise<void> {
  boolRetrying.value = true;
  try {
    await sessionStore.refreshSession();
  } finally {
    boolRetrying.value = false;
  }
}
</script>

<style scoped></style>
