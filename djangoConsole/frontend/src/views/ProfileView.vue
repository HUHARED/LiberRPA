<!-- FileName: ProfileView.vue -->
<template>
  <h1 class="text-h5 mb-2">My Profile</h1>
  <p class="text-body-2 text-medium-emphasis mb-6">
    Your current identity and organization access.
  </p>
  <v-card
    variant="outlined"
    prepend-icon="mdi-account-outline"
    :title="sessionStore.session?.user.username || 'Your account'">
    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.session?.user.username || '—'"
            label="Username"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.session?.user.email"
            label="Email"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.access?.organization.name"
            label="Organization"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="sessionStore.access?.is_org_admin ? 'OrgAdmin' : 'Member'"
            label="Organization role"
            variant="plain"
            density="compact"
            hide-details
            readonly />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
  <DepartmentAccess />
</template>

<script setup lang="ts">
import DepartmentAccess from "../components/DepartmentAccess.vue";

import { useSessionStore } from "../stores/sessionStore";

const sessionStore = useSessionStore();
</script>

<style scoped></style>
