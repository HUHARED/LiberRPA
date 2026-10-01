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
            <p v-for="message in Object.values(error.fields).flat()" :key="message">
              {{ message }}
            </p>
          </v-alert>
          <v-text-field
            v-model="name"
            label="Name"
            variant="outlined"
            :rules="[validatePathName]"
            :disabled="saving" />
          <v-text-field
            v-if="queue"
            :model-value="queue.department.path"
            label="Department"
            variant="outlined"
            readonly />
          <v-select
            v-else
            v-model="departmentId"
            :items="departments"
            item-title="path"
            item-value="id"
            label="Department"
            variant="outlined"
            :rules="[(value) => !!value || 'Select a department.']"
            :disabled="saving" />
          <v-text-field :model-value="path" label="Path" variant="outlined" readonly />
          <v-alert
            v-if="queue && name !== queue.name"
            type="warning"
            variant="tonal"
            class="mb-4">
            Renaming changes the resource path. Update saved paths in your code and
            configuration.</v-alert
          >
          <v-textarea
            v-model="notes"
            label="Notes"
            variant="outlined"
            rows="3"
            maxlength="2000"
            counter="2000"
            :disabled="saving" />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="saving" @click="emit('close')"> Cancel </v-btn>
        <v-btn
          type="submit"
          form="queue-form"
          color="primary"
          variant="tonal"
          :loading="saving"
          :disabled="saving || !allowed">
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
const session = useSessionStore();
const departments = computed(() =>
  (session.access?.departments ?? []).filter(
    (department) => session.access?.is_org_admin || department.role === "developer",
  ),
);
const name = ref(props.queue?.name ?? "");
const notes = ref(props.queue?.notes ?? "");
const departmentId = ref(
  props.queue?.department.id ??
    (departments.value.some((department) => department.id === props.initialDepartmentId)
      ? props.initialDepartmentId
      : departments.value.length === 1
        ? departments.value[0]!.id
        : null),
);
const path = computed(() => {
  const department =
    props.queue?.department.path ??
    departments.value.find((entry) => entry.id === departmentId.value)?.path;
  return department ? `/${department}/${name.value}` : "";
});
const allowed = computed(
  () =>
    session.access?.business_available &&
    departments.value.some((department) => department.id === departmentId.value),
);
const error = shallowRef<ApiError | null>(null);
const saving = ref(false);
let unmounted = false;
async function submit(event: SubmitEventPromise): Promise<void> {
  if (saving.value || !allowed.value || !(await event).valid) return;
  saving.value = true;
  error.value = null;
  try {
    const response = await saveQueue(
      props.queue
        ? { name: name.value, notes: notes.value }
        : { name: name.value, notes: notes.value, department_id: departmentId.value! },
      props.queue?.id,
    );
    if (!unmounted) emit("saved", response);
  } catch (e) {
    if (!unmounted) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    saving.value = false;
  }
}
onBeforeUnmount(() => {
  unmounted = true;
});
</script>

<style scoped></style>
