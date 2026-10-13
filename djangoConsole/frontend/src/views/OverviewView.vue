<!-- FileName: OverviewView.vue -->
<template>
  <h1 class="text-h5 mb-2">Overview</h1>
  <p class="text-medium-emphasis mb-6">Your account and organization at a glance.</p>

  <v-card variant="tonal" color="primary" class="mb-4">
    <v-card-text>
      <h2 class="text-h6 mb-2">
        Welcome,
        {{
          getDisplayName(
            sessionStore.session?.user.username ?? "",
            sessionStore.session?.user.email ?? "",
          )
        }}.
      </h2>
      <p class="text-body-1 text-anywhere">
        You're signed in to
        <span class="font-weight-bold">{{ sessionStore.access?.organization.name }}.</span>
      </p>
    </v-card-text>
  </v-card>

  <v-row>
    <v-col cols="12" md="4">
      <v-card
        class="h-100"
        variant="outlined"
        title="Organization"
        prepend-icon="mdi-office-building-outline">
        <v-card-text>
          <p class="text-body-1 font-weight-bold mb-2">
            {{ sessionStore.access?.organization.name }}
          </p>
          <p class="text-medium-emphasis">Business access available</p>
        </v-card-text>
      </v-card>
    </v-col>

    <v-col cols="12" md="4">
      <v-card
        class="h-100"
        variant="outlined"
        title="Your role"
        prepend-icon="mdi-shield-account-outline">
        <v-card-text>
          <p class="text-body-1 font-weight-bold mb-2">
            {{
              sessionStore.access?.is_org_admin
                ? "Organization administrator"
                : "Organization member"
            }}
          </p>
          <p class="text-medium-emphasis">
            {{
              sessionStore.access?.is_org_admin
                ? "Manage this organization and its departments"
                : "Access follows your department assignments"
            }}
          </p>
        </v-card-text>
      </v-card>
    </v-col>

    <v-col cols="12" md="4">
      <v-card
        class="h-100"
        variant="outlined"
        title="Signed in as"
        prepend-icon="mdi-account-circle-outline">
        <v-card-text>
          <p class="text-body-1 font-weight-bold mb-2">
            {{ sessionStore.session?.user.username || "Your account" }}
          </p>
          <p class="text-medium-emphasis text-break">
            {{ sessionStore.session?.user.email }}
          </p>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
  <DepartmentAccess />
</template>

<script setup lang="ts">
import { useSessionStore } from "../stores/sessionStore";

import DepartmentAccess from "@/components/organizations/DepartmentAccess.vue";

import { getDisplayName } from "../app/formatters";

const sessionStore = useSessionStore();
</script>

<style scoped></style>
