<!-- FileName: MembersView.vue -->
<template>
  <h2 class="text-h5 mb-2">Members</h2>
  <p class="text-medium-emphasis mb-6">Accounts in this organization.</p>
  <v-alert
    v-if="strSuccessMessage"
    type="success"
    variant="tonal"
    class="mb-4"
    role="status">
    {{ strSuccessMessage }}
  </v-alert>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="memberPage" class="mt-2">
      Previously loaded members are shown and may be out of date.
    </p>
    <template #append>
      <v-btn
        variant="tonal"
        size="small"
        :disabled="boolActionBlocked"
        @click="loadMembers()">
        Retry
      </v-btn>
    </template>
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
        <div class="table-text">
          <RouterLink
            :to="{ name: 'member-details', params: { userId: item.user.id } }"
            class="text-primary text-decoration-none">
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
        <ul v-else-if="item.department_roles.length" class="list-unstyled">
          <li
            v-for="assignment in item.department_roles"
            :key="assignment.department.id"
            class="table-text py-1">
            <RouterLink
              :to="{
                name: 'department-details',
                params: { departmentId: assignment.department.id },
              }"
              class="text-primary text-decoration-none">
              {{ assignment.department.path }}
            </RouterLink>
            <span class="text-capitalize">— {{ assignment.role }}</span>
          </li>
        </ul>
        <span v-else class="text-medium-emphasis">No department access</span>
      </template>
      <template #item.notes="{ item }">
        <div class="table-text notes-summary" :title="item.notes">
          {{ item.notes || "—" }}
        </div>
      </template>
      <template #item.joined_at="{ item }">
        {{ formatDateTime(item.joined_at, strTimeZone) }}
      </template>
      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="'Edit'"
            variant="text"
            size="small"
            :disabled="boolActionBlocked"
            :aria-label="`Edit membership for ${item.user.email}`"
            icon="mdi-pencil-outline"
            @click="openEdit(item.user)" />
          <v-btn
            v-if="item.user.id !== sessionStore.session?.user.id"
            v-tooltip:bottom="'Delete Account'"
            color="error"
            variant="text"
            size="small"
            :disabled="boolActionBlocked"
            :aria-label="`Delete account ${item.user.email}`"
            icon="mdi-account-remove-outline"
            @click="openDelete(item.user)" />
        </div>
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
          :disabled="boolActionBlocked"
          density="comfortable"
          aria-label="Member pages"
          @update:model-value="loadMembers" />
      </div>
    </template>
  </v-card>
  <MemberInvitations />
  <MembershipFormDialog
    v-if="editTarget"
    :member="editTarget"
    @close="editTarget = null"
    @saved="handleMembershipSaved" />
  <MemberDeleteDialog
    v-if="deleteTarget"
    :user="deleteTarget"
    @close="deleteTarget = null"
    @deleted="handleMemberDeleted" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { RouterLink } from "vue-router";

import MembershipFormDialog from "@/components/organizations/MembershipFormDialog.vue";
import MemberDeleteDialog from "@/components/organizations/MemberDeleteDialog.vue";
import MemberInvitations from "@/components/organizations/MemberInvitations.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getMemberList } from "@/api/members";
import type { UserResponse, MemberListResponse } from "@/api/generated/browserApi";
import { formatDateTime } from "@/app/formatters";

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const arrHeader = computed(() => [
  { title: "Account", key: "account", minWidth: 240 },
  { title: "Roles / Departments", key: "roles", minWidth: 240 },
  { title: "Notes", key: "notes", minWidth: 200 },
  { title: `Joined At (${strTimeZone.value})`, key: "joined_at", minWidth: 240 },
  { title: "Actions", key: "actions", width: 112 },
]);
const memberPage = shallowRef<MemberListResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const editTarget = shallowRef<UserResponse | null>(null);
const deleteTarget = shallowRef<UserResponse | null>(null);
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const boolActionBlocked = computed(
  () =>
    boolLoading.value ||
    editTarget.value !== null ||
    deleteTarget.value !== null ||
    !boolCanManage.value,
);
const strSuccessMessage = ref("");
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;
let intRequestedPage = 1;

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
      editTarget.value = null;
      deleteTarget.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

function openEdit(user: UserResponse): void {
  if (boolActionBlocked.value) return;
  strSuccessMessage.value = "";
  editTarget.value = user;
}

function openDelete(user: UserResponse): void {
  if (boolActionBlocked.value || user.id === sessionStore.session?.user.id) return;
  strSuccessMessage.value = "";
  deleteTarget.value = user;
}

async function handleMembershipSaved(): Promise<void> {
  strSuccessMessage.value = `Membership for ${editTarget.value?.email} updated.`;
  editTarget.value = null;
  const intCurrentRevision = intRequestRevision;
  // Refresh permissions first because a successful self-demotion removes administration access.
  await sessionStore.refreshSession();
  if (intCurrentRevision === intRequestRevision && boolCanManage.value) await loadMembers();
}

async function handleMemberDeleted(user: UserResponse): Promise<void> {
  deleteTarget.value = null;
  strSuccessMessage.value = `Account ${user.email} deleted.`;
  if (memberPage.value)
    memberPage.value = {
      ...memberPage.value,
      members: memberPage.value.members.filter((member) => member.user.id !== user.id),
      pagination: {
        ...memberPage.value.pagination,
        total_count: memberPage.value.pagination.total_count - 1,
      },
    };
  strUpdatedAt.value = null;
  await loadMembers();
}

onMounted(() => void loadMembers());
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped></style>
