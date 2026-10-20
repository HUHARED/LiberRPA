<!-- FileName: SignInView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-2">Sign in to Console</h1>

    <p class="text-medium-emphasis mb-6">
      Enter your account details to open your workspace.
    </p>

    <SignInForm />

    <v-btn
      :to="{ name: 'forgot-password' }"
      variant="tonal"
      prepend-icon="mdi-lock-question"
      block
      class="mt-3"
      :disabled="sessionStore.busy">
      Forgot Password
    </v-btn>

    <v-divider class="my-4" />

    <p class="text-medium-emphasis">
      Use the email address associated with your organization.
    </p>

    <v-btn
      :to="{ name: 'create-organization' }"
      variant="tonal"
      prepend-icon="mdi-plus"
      block
      class="mt-3"
      :disabled="sessionStore.busy">
      Create Organization
    </v-btn>
  </AuthLayout>
</template>

<script setup lang="ts">
import AuthLayout from "@/layouts/AuthLayout.vue";
import SignInForm from "@/components/accounts/SignInForm.vue";

import { useSessionStore } from "@/stores/sessionStore";

const sessionStore = useSessionStore();
</script>

<style scoped></style>
