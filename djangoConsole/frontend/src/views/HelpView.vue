<!-- FileName: HelpView.vue -->
<template>
  <h1 class="text-h5 mb-2">Help & About</h1>
  <p class="text-medium-emphasis mb-6">A workspace for your automation team.</p>
  <v-card variant="outlined">
    <v-card-text class="text-body-1">
      <BrandMark class="mb-4" />
      <p class="mb-6">
        LiberRPA is free and open-source automation software. Console connects your
        organization, Executors, and shared automation resources.
      </p>
      <h2 class="text-h6 mb-2">Account and department access</h2>
      <p class="mb-6">
        Sign in with your account's email address. An organization administrator manages
        your department assignments and roles.
      </p>
      <h2 class="text-h6 mb-2">Using a shared computer</h2>
      <p class="mb-6">
        Leave Remember me unchecked and sign out when you finish. Sign Out also ends the
        session in other tabs of this browser.
      </p>
      <h2 class="text-h6 mb-2">Connection problems</h2>
      <p>
        Check your connection and try again. If the problem continues, contact your service
        administrator.
      </p>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import BrandMark from "@/components/common/BrandMark.vue";
</script>

<style scoped></style>
