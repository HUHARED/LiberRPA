<!-- FileName: RunEmailRecipientsView.vue -->
<template>
  <div class="d-flex align-center ga-3 mb-4">
    <h2 class="text-h6">Run Email Recipients</h2>
    <v-spacer />
    <v-btn color="primary" variant="tonal" @click="openForm(null)">Add Email</v-btn>
    <v-btn variant="tonal" :loading="boolLoading" @click="load">Refresh</v-btn>
  </div>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4">
    {{ strSuccess }}
  </v-alert>
  <v-row class="mb-4">
    <v-col cols="12" md="8">
      <v-text-field v-model="strSearch" label="Email" hide-details />
    </v-col>
    <v-col cols="12" md="4">
      <v-select
        v-model="strStatus"
        :items="ARR_STATUS"
        label="Status"
        hide-details
        @update:model-value="load" />
    </v-col>
  </v-row>
  <v-data-table
    :headers="ARR_HEADER"
    :items="arrFiltered"
    :items-per-page="50"
    :items-per-page-options="[50]"
    :loading="boolLoading">
    <template #item.status="{ item }">
      {{ item.verified_at ? "Verified" : "Pending" }}
    </template>
    <template #item.actions="{ item }">
      <div class="d-flex">
        <v-btn size="small" variant="text" @click="openForm(item)">Edit Notes</v-btn>
        <v-btn
          v-if="!item.verified_at"
          size="small"
          variant="text"
          :disabled="boolBusy"
          @click="resend(item.id)">
          Resend Verification Email
        </v-btn>
        <v-btn size="small" variant="text" color="error" @click="recipientDelete = item">
          Delete
        </v-btn>
      </div>
    </template>
  </v-data-table>
  <v-dialog v-model="boolForm" persistent max-width="640">
    <v-card>
      <v-card-title>{{ recipientEdit ? "Edit Notes" : "Add Email" }}</v-card-title>
      <v-card-text>
        <v-form ref="form">
          <v-alert v-if="strFormError" type="error" variant="tonal" class="mb-4">
            {{ strFormError }}
          </v-alert>
          <v-text-field
            v-model="strEmail"
            label="Email"
            type="email"
            :readonly="!!recipientEdit"
            :rules="[(value) => !!value.trim() || 'Enter an email address.']" />
          <v-textarea v-model="strNotes" label="Notes (optional)" rows="3" />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolBusy" @click="boolForm = false">Cancel</v-btn>
        <v-btn color="primary" :loading="boolBusy" @click="save">
          {{ recipientEdit ? "Save" : "Add" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog :model-value="!!recipientDelete" persistent max-width="680">
    <v-card>
      <v-card-title>Delete Email</v-card-title>
      <v-card-text>
        <p>
          Delete {{ recipientDelete?.email }}? References from packages, schedules, active
          Jobs and pending messages must be removed first. Verification links become
          invalid.
        </p>
        <v-alert v-if="strDeleteError" type="error" variant="tonal" class="mt-4">
          {{ strDeleteError }}
        </v-alert>
        <v-list v-if="arrReference.length">
          <v-list-item
            v-for="reference in arrReference"
            :key="`${reference.kind}:${reference.id}`"
            :title="reference.name"
            :subtitle="reference.department"
            :to="getReferenceLocation(reference)" />
        </v-list>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          :disabled="boolBusy"
          @click="
            recipientDelete = null;
            strDeleteError = '';
            arrReference = [];
          ">
          Cancel
        </v-btn>
        <v-btn color="error" :loading="boolBusy" @click="remove">Delete</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { VForm } from "vuetify/components";
import {
  getRunEmailRecipients,
  saveRunEmailRecipient,
  actOnRunEmailRecipient,
  type RunEmailRecipient,
} from "@/api/runEmail";
import { getApiError } from "@/api/errors";
import { isRecord } from "@/api/responses";
interface RecipientReference {
  kind: string;
  id: string;
  name: string;
  department: string;
}
const ARR_STATUS = [
  { title: "All", value: "all" },
  { title: "Pending", value: "pending" },
  { title: "Verified", value: "verified" },
];
const ARR_HEADER = [
  { title: "Email", key: "email" },
  { title: "Status", key: "status" },
  { title: "Notes", key: "notes" },
  { title: "Actions", key: "actions", sortable: false },
];
const form = ref<InstanceType<typeof VForm> | null>(null);
const arrRecipient = ref<RunEmailRecipient[]>([]);
const strSearch = ref("");
const strStatus = ref<"all" | "pending" | "verified">("all");
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolForm = ref(false);
const recipientEdit = ref<RunEmailRecipient | null>(null);
const recipientDelete = ref<RunEmailRecipient | null>(null);
const strEmail = ref("");
const strNotes = ref("");
const strError = ref("");
const strFormError = ref("");
const strDeleteError = ref("");
const strSuccess = ref("");
const arrReference = ref<RecipientReference[]>([]);
const arrFiltered = computed(() =>
  arrRecipient.value.filter((recipient) =>
    recipient.email.toLocaleLowerCase().includes(strSearch.value.toLocaleLowerCase()),
  ),
);
function getReferenceLocation(reference: RecipientReference): RouteLocationRaw | undefined {
  if (reference.kind === "package")
    return { name: "package-details", params: { packageId: reference.id } };
  if (reference.kind === "schedule")
    return { name: "schedule-details", params: { scheduleId: reference.id } };
  return undefined;
}
async function load(): Promise<void> {
  boolLoading.value = true;
  strError.value = "";
  try {
    arrRecipient.value = (await getRunEmailRecipients(strStatus.value)).recipients;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
}
function openForm(recipient: RunEmailRecipient | null): void {
  recipientEdit.value = recipient;
  strEmail.value = recipient?.email ?? "";
  strNotes.value = recipient?.notes ?? "";
  strFormError.value = "";
  boolForm.value = true;
}
async function save(): Promise<void> {
  if (!(await form.value?.validate())?.valid) return;
  boolBusy.value = true;
  strFormError.value = "";
  try {
    await saveRunEmailRecipient(
      recipientEdit.value?.id ?? null,
      strEmail.value,
      strNotes.value,
    );
    boolForm.value = false;
    strSuccess.value = recipientEdit.value
      ? "Notes saved."
      : "Address added. Ask the recipient to confirm the verification email.";
    await load();
  } catch (e) {
    strFormError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function resend(id: string): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    await actOnRunEmailRecipient(id, "resend");
    strSuccess.value = "Verification email requested.";
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function remove(): Promise<void> {
  if (!recipientDelete.value) return;
  boolBusy.value = true;
  strDeleteError.value = "";
  try {
    await actOnRunEmailRecipient(recipientDelete.value.id, "delete");
    recipientDelete.value = null;
    await load();
  } catch (e) {
    const error = getApiError(e);
    strDeleteError.value = error.message;
    const payload = error.responsePayload;
    if (
      isRecord(payload) &&
      isRecord(payload.error) &&
      Array.isArray(payload.error.references)
    )
      arrReference.value = payload.error.references as RecipientReference[];
  } finally {
    boolBusy.value = false;
  }
}
onMounted(() => void load());
</script>
<style scoped></style>
