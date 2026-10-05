<!-- FileName: QueueFormDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="660"
    aria-labelledby="queue-form-title">
    <v-card>
      <v-card-title id="queue-form-title">
        {{ queue ? "Edit Queue" : "New Queue" }}
      </v-card-title>
      <v-card-text>
        <v-form id="queue-form" validate-on="submit" @submit.prevent="submit">
          <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
            {{ error.message }}
            <p v-for="strMessage in Object.values(error.fields).flat()" :key="strMessage">
              {{ strMessage }}
            </p>
          </v-alert>
          <v-text-field
            v-model="strName"
            label="Name"
            variant="outlined"
            :rules="[validatePathName]"
            :disabled="boolSaving" />
          <v-text-field
            v-if="queue"
            :model-value="queue.department.path"
            label="Department"
            variant="outlined"
            readonly />
          <v-select
            v-else
            v-model="strDepartmentId"
            :items="departments"
            item-title="path"
            item-value="id"
            label="Department"
            variant="outlined"
            :rules="[(value) => !!value || 'Select a department.']"
            :disabled="boolSaving" />
          <v-text-field :model-value="strPath" label="Path" variant="outlined" readonly />
          <v-alert
            v-if="queue && strName !== queue.name"
            type="warning"
            variant="tonal"
            class="mb-4">
            Renaming changes the resource path. Update saved paths in your code and
            configuration.
          </v-alert>
          <v-textarea
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            maxlength="2000"
            counter="2000"
            :disabled="boolSaving" />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolSaving" @click="emit('close')">Cancel</v-btn>
        <v-btn
          type="submit"
          form="queue-form"
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="boolSaving || !boolAllowed">
          {{ queue ? "Save" : "Create" }}
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

import { getApiError, type ApiError } from "@/api/errors";
import { saveQueue } from "@/api/dataQueues";
import type { QueueEntryResponse, QueueDetailsResponse } from "@/api/generated/browserApi";

const props = defineProps<{ queue?: QueueEntryResponse; initialDepartmentId?: string }>();
const emit = defineEmits<{ close: []; saved: [response: QueueDetailsResponse] }>();
const sessionStore = useSessionStore();
const departments = computed(() =>
  (sessionStore.access?.departments ?? []).filter(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);
const strName = ref(props.queue?.name ?? "");
const strNotes = ref(props.queue?.notes ?? "");
const strDepartmentId = ref(
  props.queue?.department.id ??
    (departments.value.some((department) => department.id === props.initialDepartmentId)
      ? props.initialDepartmentId
      : departments.value.length === 1
        ? departments.value[0]!.id
        : null),
);
const strPath = computed(() => {
  const strDepartmentPath =
    props.queue?.department.path ??
    departments.value.find((entry) => entry.id === strDepartmentId.value)?.path;
  return strDepartmentPath ? `/${strDepartmentPath}/${strName.value}` : "";
});
const boolAllowed = computed(
  () =>
    sessionStore.access?.business_available &&
    departments.value.some((department) => department.id === strDepartmentId.value),
);
const error = shallowRef<ApiError | null>(null);
const boolSaving = ref(false);
let boolUnmounted = false;
async function submit(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value || !boolAllowed.value || !(await event).valid) return;
  boolSaving.value = true;
  error.value = null;
  try {
    const response = await saveQueue(
      props.queue
        ? { name: strName.value, notes: strNotes.value }
        : {
            name: strName.value,
            notes: strNotes.value,
            department_id: strDepartmentId.value!,
          },
      props.queue?.id,
    );
    if (!boolUnmounted) emit("saved", response);
  } catch (e) {
    if (!boolUnmounted) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolSaving.value = false;
  }
}
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
