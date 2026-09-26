<!-- FileName: MemberDetailsView.vue -->
<template>
  <v-btn
    :to="{ name: 'members' }"
    variant="text"
    prepend-icon="mdi-arrow-left"
    class="mb-4">
    Back to Members
  </v-btn>
  <v-row align="center" class="mb-4">
    <v-col>
      <h2 class="text-h5 mb-2 member-text">
        {{
          memberInfo ? memberInfo.user.username || memberInfo.user.email : "Member Details"
        }}
      </h2>
      <p class="text-body-2 text-medium-emphasis">Member Details</p>
    </v-col>
    <v-col cols="auto" class="d-flex flex-wrap ga-2">
      <v-btn
        v-if="memberInfo && memberInfo.user.id === sessionStore.session?.user.id"
        :to="{ name: 'my-profile' }"
        variant="tonal"
        prepend-icon="mdi-account-circle-outline">
        My Profile
      </v-btn>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="boolLoading"
        :disabled="boolLoading"
        @click="loadMemberDetails">
        Refresh
      </v-btn>
    </v-col>
  </v-row>
  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{
      requestError.statusCode === 404
        ? "This member does not exist or is no longer available in this organization."
        : requestError.message
    }}
    <p v-if="memberInfo" class="mt-2">
      Previously loaded details are shown. Refresh to try again.
    </p>
  </v-alert>
  <v-progress-linear
    v-if="boolLoading"
    indeterminate
    color="primary"
    class="mb-4"
    aria-label="Loading member details" />
  <template v-if="memberInfo">
    <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
      Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
    </p>
    <v-card variant="outlined" class="mb-4" :aria-busy="boolLoading">
      <v-card-title>Member Information</v-card-title>
      <v-card-text>
        <dl class="member-fields">
          <div>
            <dt>Account</dt>
            <dd>
              {{ memberInfo.user.username || memberInfo.user.email }}
              <p v-if="memberInfo.user.username" class="text-body-2 text-medium-emphasis">
                {{ memberInfo.user.email }}
              </p>
            </dd>
          </div>
          <div>
            <dt>Organization Role</dt>
            <dd>{{ memberInfo.is_org_admin ? "OrgAdmin" : "Member" }}</dd>
          </div>
          <div>
            <dt>Joined At ({{ strTimeZone }})</dt>
            <dd>{{ formatDateTime(memberInfo.joined_at, strTimeZone) }}</dd>
          </div>
          <div class="full-width-field">
            <dt>Notes</dt>
            <dd class="member-notes">{{ memberInfo.notes || "—" }}</dd>
          </div>
        </dl>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" :aria-busy="boolLoading">
      <v-card-title>Department Roles</v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">
          {{
            memberInfo.is_org_admin
              ? "Organization administrators can access all departments. These explicit assignments are retained if the administrator role is removed."
              : "Only explicitly assigned department roles are listed. Access is not inherited by subdepartments."
          }}
        </p>
        <v-data-table
          :headers="ARR_ROLE_HEADER"
          :items="memberInfo.department_roles"
          :items-per-page="50"
          :items-per-page-options="[50]"
          :hide-default-footer="memberInfo.department_roles.length <= 50"
          :mobile-breakpoint="600"
          item-value="department.id"
          disable-sort>
          <template #item.department="{ item }">
            <RouterLink
              :to="{
                name: 'department-details',
                params: { departmentId: item.department.id },
              }"
              class="member-text text-primary">
              {{ item.department.path }}
            </RouterLink>
          </template>
          <template #item.role="{ item }">
            <span class="text-capitalize">{{ item.role }}</span>
          </template>
          <template #no-data>
            {{
              memberInfo.is_org_admin
                ? "No explicit department roles."
                : "No department access."
            }}
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { getMemberDetails } from "../api/members";
import type { MemberResponse } from "../api/generated/browserApi";
import { formatDateTime } from "../app/navigation";

const props = defineProps<{ userId: string }>();
const ARR_ROLE_HEADER = [
  { title: "Department", key: "department", minWidth: 240 },
  { title: "Role", key: "role", minWidth: 120 },
];

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const memberInfo = shallowRef<MemberResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const boolLoading = ref(false);
const strUpdatedAt = ref<string | null>(null);
let intRequestRevision = 0;

// TODO: Add membership editing and account deletion through the existing administration APIs.
// TODO: Reuse the API key metadata table here when the API Keys page is implemented.
async function loadMemberDetails(): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const response = await getMemberDetails(props.userId);
    if (intCurrentRevision !== intRequestRevision) return;
    memberInfo.value = response.member;
    strUpdatedAt.value = new Date().toISOString();
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    requestError.value = getApiError(e);
    if ([401, 403, 404].includes(requestError.value.statusCode)) {
      memberInfo.value = null;
      strUpdatedAt.value = null;
      if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolLoading.value = false;
  }
}

watch(
  () => props.userId,
  () => {
    memberInfo.value = null;
    strUpdatedAt.value = null;
    void loadMemberDetails();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  intRequestRevision += 1;
});
</script>

<style scoped>
.member-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 20px;
}

.member-fields dt {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  margin-bottom: 4px;
}

.member-fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.full-width-field {
  grid-column: 1 / -1;
}

.member-text {
  overflow-wrap: anywhere;
}

.member-notes {
  white-space: pre-wrap;
}
</style>
