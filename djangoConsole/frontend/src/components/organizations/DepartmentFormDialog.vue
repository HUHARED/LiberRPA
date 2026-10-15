<!-- FileName: DepartmentFormDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="640"
    aria-labelledby="department-form-title">
    <v-card>
      <v-card-title id="department-form-title">
        {{
          department
            ? "Edit Department"
            : strParentId === null
              ? "New Department"
              : "New Subdepartment"
        }}
      </v-card-title>

      <v-card-text>
        <v-form
          id="department-form"
          validate-on="submit"
          @submit.prevent="submitDepartment">
          <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
            {{
              department ? "The update was not confirmed." : "Creation was not confirmed."
            }}
            {{ saveError.message }}
            <p
              v-for="strMessage in saveError.fields.__all__"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
            </p>
          </v-alert>

          <v-text-field
            v-model="strName"
            label="Name"
            variant="outlined"
            :rules="[validatePathName]"
            :error-messages="saveError?.fields.name ?? []"
            :disabled="boolSaving"
            required
            @update:model-value="saveError = null" />

          <v-select
            v-model="strParentId"
            :items="arrParentOption"
            item-title="path"
            item-value="id"
            label="Parent Department"
            variant="outlined"
            :rules="[validateParent]"
            :error-messages="saveError?.fields.parent_id ?? []"
            :disabled="boolSaving"
            @update:model-value="saveError = null" />

          <v-text-field
            v-if="department"
            :model-value="department.path"
            label="Current Path"
            variant="outlined"
            readonly />

          <v-text-field
            :model-value="strNewPath"
            :label="department ? 'New Path' : 'Path'"
            variant="outlined"
            readonly />

          <v-alert v-if="boolPathChanged" type="warning" variant="tonal" class="mb-4">
            Subdepartment and resource paths will also change. Update any paths used in
            code, arguments, and templates.
          </v-alert>

          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            counter="2000"
            maxlength="2000"
            :error-messages="saveError?.fields.notes ?? []"
            :disabled="boolSaving"
            @update:model-value="saveError = null" />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="closeForm">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          type="submit"
          form="department-form"
          color="primary"
          variant="tonal"
          :prepend-icon="department ? 'mdi-content-save-outline' : 'mdi-plus'"
          :loading="boolSaving"
          :disabled="boolSaving || !boolCanManage">
          {{ department ? "Save" : "Create" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { validatePathName } from "@/app/validators";

import { type ApiError, getApiError } from "@/api/errors";
import { createDepartment, updateDepartment } from "@/api/departments";
import type {
  DepartmentListEntryResponse,
  DepartmentUpdateRequest,
  DepartmentRecordResponse,
} from "@/api/generated/browserApi";

const props = defineProps<{
  departments: DepartmentListEntryResponse[];
  department?: DepartmentListEntryResponse;
  parentId?: string | null;
}>();

const emit = defineEmits<{
  close: [];
  saved: [department: DepartmentRecordResponse];
}>();

const sessionStore = useSessionStore();

const boolCanManage = computed(
  () => sessionStore.access?.is_org_admin && sessionStore.access.business_available,
);

const strName = ref<string | null>(props.department?.name ?? "");

const strParentId = ref<string | null>(
  props.department ? props.department.parent_id : (props.parentId ?? null),
);

const strNotes = ref<string | null>(props.department?.notes ?? "");
const saveError = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
let boolUnmounted = false;

const arrParentOption = computed(() => [
  { id: null, path: "No parent (top level)" },
  ...props.departments.filter(
    (department) =>
      !props.department ||
      (department.id !== props.department.id &&
        !department.path.startsWith(`${props.department.path}/`)),
  ),
]);

const strNewPath = computed(() => {
  if (!strName.value) return "";
  if (strParentId.value === null) return strName.value;
  const parent = arrParentOption.value.find(
    (department) => department.id === strParentId.value,
  );
  return parent ? `${parent.path}/${strName.value}` : "";
});

const boolPathChanged = computed(
  () =>
    !!props.department && !!strNewPath.value && strNewPath.value !== props.department.path,
);

function validateParent(value: string | null): true | string {
  return arrParentOption.value.some((department) => department.id === value)
    ? true
    : "Select an available parent department or the top level.";
}

function closeForm(): void {
  if (!boolSaving.value) emit("close");
}

async function submitDepartment(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value) return;
  const validationResult = await event;
  if (!validationResult.valid || boolSaving.value || !boolCanManage.value || boolUnmounted)
    return;
  boolSaving.value = true;
  saveError.value = null;
  try {
    const departmentRequest: DepartmentUpdateRequest = {
      name: strName.value ?? "",
      parent_id: strParentId.value,
      notes: strNotes.value ?? "",
    };
    const response = props.department
      ? await updateDepartment(props.department.id, departmentRequest)
      : await createDepartment(departmentRequest);
    if (!boolUnmounted) emit("saved", response.department);
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value = getApiError(e);
    if (saveError.value.statusCode === 403) await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
