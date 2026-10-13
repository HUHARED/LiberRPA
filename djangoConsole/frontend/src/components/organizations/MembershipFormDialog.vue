<!-- FileName: MembershipFormDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="760"
    aria-labelledby="membership-form-title">
    <v-card>
      <v-card-title id="membership-form-title">
        {{ member ? "Edit Membership" : "Invite Member" }}
      </v-card-title>
      <v-card-text>
        <v-progress-linear
          v-if="boolLoading"
          indeterminate
          color="primary"
          class="mb-4"
          aria-label="Loading membership form" />
        <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ requestError.message }}
        </v-alert>
        <v-form
          v-if="arrDepartment !== null"
          id="membership-form"
          :novalidate="false"
          validate-on="submit"
          @submit.prevent="submitMembership">
          <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
            {{
              member ? "The update was not confirmed." : "The invitation was not confirmed."
            }}
            {{ saveError.message }}
            <p
              v-for="strMessage in saveError.fields.__all__"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
            </p>
            <p v-if="intRetrySeconds" class="mt-2">
              Try again in {{ intRetrySeconds }} seconds.
            </p>
          </v-alert>
          <v-text-field
            v-if="member"
            :model-value="strAccount"
            label="Account"
            variant="outlined"
            readonly />
          <v-text-field
            v-else
            v-model="strEmail"
            label="Email"
            type="email"
            autocomplete="email"
            variant="outlined"
            maxlength="254"
            :rules="[validateEmail]"
            :error-messages="saveError?.fields.email ?? []"
            :disabled="boolSaving"
            required />
          <v-switch
            v-model="boolOrgAdmin"
            label="OrgAdmin"
            color="primary"
            :disabled="boolSaving"
            :error-messages="saveError?.fields.is_org_admin ?? []" />
          <v-alert v-if="boolOrgAdmin" type="info" variant="tonal" class="mb-4">
            Organization administrators can access all departments. Any existing explicit
            department roles are kept and will reappear when OrgAdmin is turned off.
          </v-alert>
          <v-alert
            v-if="member && member.id === sessionStore.session?.user.id && !boolOrgAdmin"
            type="warning"
            variant="tonal"
            class="mb-4">
            Saving will remove your organization administration access. You will keep only
            your explicit department roles.
          </v-alert>
          <div v-show="!boolOrgAdmin" class="mb-4">
            <h3 class="text-subtitle-1 mb-2">Department Roles</h3>
            <v-alert
              v-if="saveError?.fields.department_roles"
              type="error"
              variant="tonal"
              class="mb-3">
              <p v-for="strMessage in saveError.fields.department_roles" :key="strMessage">
                {{ strMessage }}
              </p>
            </v-alert>
            <v-table>
              <thead>
                <tr>
                  <th scope="col">Department</th>
                  <th scope="col">Role</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(assignment, intIndex) in arrRole"
                  :key="assignment.department_id">
                  <td class="department-cell">
                    <v-select
                      v-model="assignment.department_id"
                      :items="getDepartmentOptions(assignment.department_id)"
                      item-title="path"
                      item-value="id"
                      :aria-label="`Department ${intIndex + 1}`"
                      variant="outlined"
                      density="compact"
                      hide-details
                      :disabled="boolSaving" />
                  </td>
                  <td>
                    <v-select
                      v-model="assignment.role"
                      :items="ARR_ROLE_OPTION"
                      :aria-label="`Role ${intIndex + 1}`"
                      variant="outlined"
                      density="compact"
                      hide-details
                      :disabled="boolSaving" />
                  </td>
                  <td>
                    <v-btn
                      v-tooltip:bottom="'Remove department role'"
                      variant="text"
                      icon="mdi-delete-outline"
                      size="small"
                      :disabled="boolSaving"
                      :aria-label="`Remove department role ${intIndex + 1}`"
                      @click="arrRole.splice(intIndex, 1)" />
                  </td>
                </tr>
                <tr v-if="!arrRole.length">
                  <td colspan="3" class="text-medium-emphasis py-4">
                    No department access. A member can be saved without department roles.
                  </td>
                </tr>
              </tbody>
            </v-table>
            <v-btn
              variant="tonal"
              prepend-icon="mdi-plus"
              class="mt-3"
              :disabled="boolSaving || arrRole.length >= arrDepartment.length"
              @click="addDepartment">
              Add Department
            </v-btn>
          </div>
          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            maxlength="2000"
            counter="2000"
            :error-messages="saveError?.fields.notes ?? []"
            :disabled="boolSaving" />
          <p v-if="!member">The recipient will receive a link to create an account.</p>
        </v-form>
      </v-card-text>
      <v-card-actions class="flex-wrap ga-2">
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolSaving" @click="closeForm">Cancel</v-btn>
        <v-btn
          v-if="requestError"
          variant="tonal"
          :disabled="boolLoading || !boolCanManage"
          @click="loadForm">
          Retry
        </v-btn>
        <v-btn
          type="submit"
          form="membership-form"
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="
            boolLoading ||
            boolSaving ||
            arrDepartment === null ||
            !boolCanManage ||
            intRetrySeconds > 0
          ">
          {{ member ? "Save" : "Invite Member" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

import { type ApiError, getApiError } from "@/api/errors";
import { getDepartmentList } from "@/api/departments";
import { getMemberDetails, updateMembership } from "@/api/members";
import { createInvitation } from "@/api/invitations";
import type {
  UserResponse,
  DepartmentListEntryResponse,
  DepartmentRoleRequest,
  InvitationResponse,
  MembershipUpdateRequest,
  MembershipRecordResponse,
} from "@/api/generated/browserApi";

const props = defineProps<{ member?: UserResponse }>();
const emit = defineEmits<{
  close: [];
  saved: [member: MembershipRecordResponse];
  invited: [invitation: InvitationResponse];
}>();
const ARR_ROLE_OPTION = [
  { title: "Developer", value: "developer" },
  { title: "Operator", value: "operator" },
];
const sessionStore = useSessionStore();
const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const arrDepartment = shallowRef<DepartmentListEntryResponse[] | null>(null);
const strAccount = ref("");
const strEmail = ref("");
const boolOrgAdmin = ref(false);
const arrRole = ref<DepartmentRoleRequest[]>([]);
const strNotes = ref("");
const boolLoading = ref(false);
const boolSaving = ref(false);
const requestError = shallowRef<ApiError | null>(null);
const saveError = shallowRef<ApiError | null>(null);
let boolUnmounted = false;

async function loadForm(): Promise<void> {
  if (boolUnmounted || boolLoading.value || boolSaving.value || !boolCanManage.value)
    return;
  boolLoading.value = true;
  requestError.value = null;
  try {
    const [departments, details] = await Promise.all([
      getDepartmentList(),
      props.member ? getMemberDetails(props.member.id) : Promise.resolve(null),
    ]);
    if (boolUnmounted) return;
    arrDepartment.value = departments.departments;
    if (details) {
      strAccount.value = `${details.member.user.username} (${details.member.user.email})`;
      boolOrgAdmin.value = details.member.is_org_admin;
      arrRole.value = details.member.department_roles.map((assignment) => ({
        department_id: assignment.department.id,
        role: assignment.role,
      }));
      strNotes.value = details.member.notes;
    }
  } catch (e) {
    if (boolUnmounted) return;
    requestError.value = getApiError(e);
    if (requestError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolLoading.value = false;
  }
}

function getDepartmentOptions(departmentId: string): DepartmentListEntryResponse[] {
  return (arrDepartment.value ?? []).filter(
    (department) =>
      department.id === departmentId ||
      !arrRole.value.some((assignment) => assignment.department_id === department.id),
  );
}

function addDepartment(): void {
  if (boolSaving.value || boolOrgAdmin.value) return;
  const department = (arrDepartment.value ?? []).find(
    (department) =>
      !arrRole.value.some((assignment) => assignment.department_id === department.id),
  );
  if (department) arrRole.value.push({ department_id: department.id, role: "operator" });
}

function validateEmail(value: string): true | string {
  return value.trim() ? true : "Enter the recipient's email address.";
}

function closeForm(): void {
  if (!boolSaving.value) emit("close");
}

async function submitMembership(event: SubmitEventPromise): Promise<void> {
  if (
    boolUnmounted ||
    boolLoading.value ||
    boolSaving.value ||
    !boolCanManage.value ||
    arrDepartment.value === null ||
    intRetrySeconds.value > 0
  )
    return;
  const validation = await event;
  if (
    !validation.valid ||
    boolUnmounted ||
    boolLoading.value ||
    boolSaving.value ||
    !boolCanManage.value ||
    arrDepartment.value === null ||
    intRetrySeconds.value > 0
  )
    return;
  boolSaving.value = true;
  saveError.value = null;
  const request: MembershipUpdateRequest = {
    is_org_admin: boolOrgAdmin.value,
    department_roles: arrRole.value.map((assignment) => ({ ...assignment })),
    notes: strNotes.value,
  };
  try {
    if (props.member) {
      const response = await updateMembership(props.member.id, request);
      if (!boolUnmounted) emit("saved", response.member);
    } else {
      const response = await createInvitation({ ...request, email: strEmail.value.trim() });
      if (!boolUnmounted) emit("invited", response.invitation);
    }
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    setRetryDelay(saveError.value.retryAfterSeconds);
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

onMounted(() => void loadForm());
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped>
.department-cell {
  width: 55%;
  min-width: 240px;
}
</style>
