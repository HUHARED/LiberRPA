<!-- FileName: SignInView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-6">Sign in to Console</h1>

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
