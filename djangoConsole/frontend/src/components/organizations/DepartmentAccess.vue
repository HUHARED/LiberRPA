<!-- FileName: DepartmentAccess.vue -->
<template>
  <v-card variant="outlined" class="mt-4" aria-labelledby="department-heading">
    <v-card-title class="d-flex flex-wrap align-center ga-2">
      <h2 id="department-heading" class="text-h6">Departments</h2>

      <v-spacer />

      <v-chip size="small" variant="tonal">
        {{
          sessionStore.access?.is_org_admin
            ? "All departments"
            : `${sessionStore.access?.departments.length ?? 0} departments`
        }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <p>
        {{
          sessionStore.access?.is_org_admin
            ? "You have organization administrator access to all departments."
            : "Your current department assignments and roles."
        }}
      </p>
    </v-card-text>

    <v-list v-if="sessionStore.access?.departments.length" density="compact">
      <v-list-item
        v-for="departmentInfo in sessionStore.access.departments"
        :key="departmentInfo.id"
        :title="departmentInfo.path"
        prepend-icon="mdi-folder-outline">
        <template #append>
          <v-chip
            size="small"
            variant="tonal"
            :color="
              sessionStore.access.is_org_admin || departmentInfo.role === 'developer'
                ? 'primary'
                : undefined
            ">
            {{
              sessionStore.access.is_org_admin
                ? "OrgAdmin"
                : departmentInfo.role === "developer"
                  ? "Developer"
                  : "Operator"
            }}
          </v-chip>
        </template>
      </v-list-item>
    </v-list>

    <v-card-text v-else>
      No department access. Ask an organization administrator to assign a role.
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { useSessionStore } from "@/stores/sessionStore";

const sessionStore = useSessionStore();
</script>

<style scoped></style>
