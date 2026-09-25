<!-- FileName: NotFoundView.vue -->
<template>
  <AuthLayout>
    <v-container class="pa-0 text-center">
      <p class="text-h4 text-medium-emphasis mb-3">404</p>
      <h1 class="text-h5 mb-3">Page not found</h1>
      <p class="text-body-2 text-medium-emphasis mb-6">
        This address does not point to an available Console page.
      </p>
      <v-btn
        color="primary"
        variant="tonal"
        :to="sessionStore.authenticated ? '/overview' : '/sign-in'">
        {{ sessionStore.authenticated ? "Open Workspace" : "Sign In" }}
      </v-btn>
    </v-container>
  </AuthLayout>
</template>

<script setup lang="ts">
import AuthLayout from "../layouts/AuthLayout.vue";

import { useSessionStore } from "../stores/sessionStore";

const sessionStore = useSessionStore();
</script>

<style scoped></style>
