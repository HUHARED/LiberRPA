<!-- FileName: MembersView.vue -->
<template>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h5 mb-2">Members</h2>
      <p class="text-body-2 text-medium-emphasis">Accounts in this organization.</p>
    </v-col>
    <v-col cols="auto">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="loadMembers()">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="memberPage" class="mt-2">
      Previously loaded members are shown. Refresh to try again.
    </p>
  </v-alert>
  <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
    Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
  </p>
  <v-card variant="outlined" :aria-busy="boolLoading">
    <v-data-table-server
      :headers="arrHeader"
      :items="memberPage?.members ?? []"
      :items-length="memberPage?.pagination.total_count ?? 0"
      :items-per-page="memberPage?.pagination.page_size ?? 50"
      :page="memberPage?.pagination.page ?? 1"
      :loading="boolLoading"
      :mobile-breakpoint="600"
      item-value="user.id"
      loading-text="Loading members…"
      disable-sort
      hide-default-footer>
      <template #item.account="{ item }">
        <div class="member-text">
          <RouterLink
            :to="{ name: 'member-details', params: { userId: item.user.id } }"
            class="text-primary font-weight-medium">
            {{ item.user.username || item.user.email }}
          </RouterLink>
          <p v-if="item.user.username" class="text-body-2 text-medium-emphasis">
            {{ item.user.email }}
          </p>
        </div>
      </template>
      <template #item.roles="{ item }">
        <template v-if="item.is_org_admin">
          <v-chip color="primary" size="small" variant="tonal">OrgAdmin</v-chip>
          <p class="text-body-2 mt-1">All departments</p>
        </template>
        <ul v-else-if="item.department_roles.length" class="department-roles">
          <li
            v-for="assignment in item.department_roles"
            :key="assignment.department.id"
            class="member-text py-1">
            <RouterLink
              :to="{
                name: 'department-details',
                params: { departmentId: assignment.department.id },
              }"
              class="text-primary">
              {{ assignment.department.path }}
            </RouterLink>
            <span class="text-capitalize"> — {{ assignment.role }}</span>
          </li>
        </ul>
        <span v-else class="text-medium-emphasis">No department access</span>
      </template>
      <template #item.notes="{ item }">
        <div class="member-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>
      <template #item.joined_at="{ item }">
        {{ formatDateTime(item.joined_at, strTimeZone) }}
      </template>
      <template #item.actions="{ item }">
        <v-btn
          :to="{ name: 'member-details', params: { userId: item.user.id } }"
          variant="text"
          size="small"
          prepend-icon="mdi-eye-outline"
          :aria-label="`View member ${item.user.email}`">
          View
        </v-btn>
      </template>
      <template #no-data>
        {{ requestError ? "The member list could not be loaded." : "No members found." }}
      </template>
    </v-data-table-server>
    <template v-if="memberPage">
      <v-divider />
      <div class="d-flex flex-wrap align-center justify-space-between ga-2 pa-3">
        <p class="text-body-2 text-medium-emphasis" aria-live="polite">
          {{ memberPage.pagination.total_count }} members · Page
          {{ memberPage.pagination.page }} of {{ memberPage.pagination.total_pages }}
        </p>
        <v-pagination
          v-if="memberPage.pagination.total_pages > 1"
          :model-value="memberPage.pagination.page"
          :length="memberPage.pagination.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          density="comfortable"
          aria-label="Member pages"
          @update:model-value="loadMembers" />
      </div>
    </template>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getMemberList } from "../api/members";
import type { MemberListResponse } from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const arrHeader = computed(() => [
  { title: "Account", key: "account", minWidth: 240 },
  { title: "Roles / Departments", key: "roles", minWidth: 240 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: `Joined At (${strTimeZone.value})`, key: "joined_at", minWidth: 240 },
  { title: "Actions", key: "actions", width: 100 },
]);
const memberPage = shallowRef<MemberListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;
let intRequestedPage = 1;

// TODO: Add member invitations and membership editing through the existing administration APIs.
async function loadMembers(pageNumber: number = intRequestedPage): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  intRequestedPage = pageNumber;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getMemberList(pageNumber);
    if (intCurrentRevision !== intRequestRevision) return;
    memberPage.value = response;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    // A removed account can leave the previously selected page outside the current list.
    if (requestError.value.code === "member_page_not_found" && pageNumber > 1) {
      await loadMembers(1);
      return;
    }
    if ([401, 403].includes(requestError.value.statusCode)) {
      memberPage.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

onMounted(() => void loadMembers());
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped>
.member-text {
  max-width: 360px;
  overflow-wrap: anywhere;
}

.department-roles {
  list-style: none;
  padding: 0;
}

.notes-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: pre-line;
}
</style>
