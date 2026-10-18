<!-- FileName: RunEmailRecipientsView.vue -->
<template>
  <div class="d-flex align-center ga-3 mb-4">
    <h2 class="text-h6">Run Email Recipients</h2>
    <v-spacer />
    <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="boolLoading" @click="load">
      Refresh
    </v-btn>

    <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openForm(null)">
      Add Email
    </v-btn>
  </div>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4">
    {{ strSuccess }}
  </v-alert>

  <p class="text-body-2 text-medium-emphasis mb-4">
    Current member emails are available automatically. Other addresses require verification.
  </p>

  <v-row class="mb-4">
    <v-col cols="12" md="8">
      <v-text-field v-model="strSearch" variant="underlined" label="Email" hide-details />
    </v-col>

    <v-col cols="12" md="4">
      <v-select
        v-model="strStatus"
        variant="underlined"
        :items="ARR_STATUS"
        label="Status"
        hide-details
        @update:model-value="load" />
    </v-col>
  </v-row>

  <v-data-table :headers="ARR_HEADER" :items="arrFiltered" :loading="boolLoading">
    <template #item.status="{ item }">
      {{ DICT_STATUS_LABEL[item.status] }}
    </template>

    <template #item.actions="{ item }">
      <div class="d-flex align-center ga-1">
        <v-btn
          v-tooltip:bottom="'Edit Notes'"
          size="small"
          variant="text"
          aria-label="Edit Notes"
          icon="mdi-note-edit-outline"
          @click="openForm(item)" />

        <v-btn
          v-if="item.status === RunEmailRecipientStatus.Pending"
          v-tooltip:bottom="'Resend Verification Email'"
          size="small"
          variant="text"
          :disabled="boolBusy"
          aria-label="Resend Verification Email"
          icon="mdi-email-sync-outline"
          @click="resend(item.id)" />

        <v-btn
          v-if="item.status !== RunEmailRecipientStatus.Member"
          v-tooltip:bottom="'Delete'"
          size="small"
          variant="text"
          color="error"
          aria-label="Delete"
          icon="mdi-delete-outline"
          @click="recipientDelete = item" />
      </div>
    </template>
  </v-data-table>

  <v-dialog v-model="boolForm" :persistent="boolBusy" max-width="640">
    <v-card>
      <v-card-title>{{ recipientEdit ? "Edit Notes" : "Add Email" }}</v-card-title>

      <v-card-text>
        <v-form ref="form">
          <v-alert v-if="strFormError" type="error" variant="tonal" class="mb-4">
            {{ strFormError }}
          </v-alert>

          <v-text-field
            v-model="strEmail"
            :variant="recipientEdit ? 'plain' : 'outlined'"
            label="Email"
            type="email"
            :readonly="!!recipientEdit"
            :rules="[(value) => !!value.trim() || 'Enter an email address.']" />

          <v-textarea
            v-model="strNotes"
            variant="outlined"
            label="Notes (optional)"
            rows="3" />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="boolForm = false">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          :prepend-icon="recipientEdit ? 'mdi-content-save-outline' : 'mdi-plus'"
          color="primary"
          :loading="boolBusy"
          @click="save">
          {{ recipientEdit ? "Save" : "Add" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog
    :model-value="!!recipientDelete"
    :persistent="boolBusy"
    max-width="680"
    @update:model-value="!$event && closeDelete()">
    <v-card>
      <v-card-title>Delete Email</v-card-title>

      <v-card-text>
        <p class="text-anywhere">
          Delete
          <span class="text-highlight font-weight-bold">{{ recipientDelete?.email }}?</span>
          References from packages, schedules, active Jobs and pending messages must be
          removed first. Verification links become invalid.
        </p>

        <v-alert v-if="strDeleteError" type="error" variant="tonal" class="mt-4">
          {{ strDeleteError }}
        </v-alert>

        <v-list v-if="arrReference.length">
          <v-list-item
            v-for="reference in arrReference"
            :key="'id' in reference ? `${reference.kind}:${reference.id}` : reference.kind"
            :subtitle="'department' in reference ? reference.department : undefined"
            :to="getReferenceLocation(reference)"
            class="text-decoration-none">
            <template #title>
              <span :class="{ 'text-primary': !!getReferenceLocation(reference) }">
                {{ reference.name }}
              </span>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="closeDelete">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          color="error"
          :loading="boolBusy"
          @click="remove">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { VForm } from "vuetify/components";

import {
  getRunEmailRecipients,
  saveRunEmailRecipient,
  actOnRunEmailRecipient,
  type RunEmailRecipientFilter,
  type RunEmailRecipient,
} from "@/api/runEmail";
import { RunEmailRecipientStatus } from "@/api/generated/browserApi";
import { getApiError } from "@/api/errors";
import { isRecord } from "@/api/responses";

type RecipientReference =
  | {
      kind: "package" | "schedule";
      id: string;
      name: string;
      department: string;
    }
  | { kind: "job" | "delivery"; name: string };

const DICT_STATUS_LABEL: Record<RunEmailRecipientStatus, string> = {
  [RunEmailRecipientStatus.Member]: "Member",
  [RunEmailRecipientStatus.Verified]: "Verified",
  [RunEmailRecipientStatus.Pending]: "Pending",
};
const ARR_STATUS = [
  { title: "All", value: "all" },
  ...Object.values(RunEmailRecipientStatus).map((status) => ({
    title: DICT_STATUS_LABEL[status],
    value: status,
  })),
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
const strStatus = ref<RunEmailRecipientFilter>("all");
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
let intLoadRequest = 0;

const arrFiltered = computed(() =>
  arrRecipient.value.filter((recipient) =>
    recipient.email.toLocaleLowerCase().includes(strSearch.value.toLocaleLowerCase()),
  ),
);

function getReferenceLocation(reference: RecipientReference): RouteLocationRaw | undefined {
  if (reference.kind === "package")
    return { name: "package-details", params: { packageId: reference.id } };
  if (reference.kind === "schedule")
    return { name: "schedule", params: { scheduleId: reference.id } };
  return undefined;
}

async function load(): Promise<void> {
  const intCurrentRequest = ++intLoadRequest;
  boolLoading.value = true;
  strError.value = "";
  try {
    const result = await getRunEmailRecipients(strStatus.value);
    if (intCurrentRequest !== intLoadRequest) return;
    arrRecipient.value = result.recipients;
  } catch (e) {
    if (intCurrentRequest === intLoadRequest) strError.value = getApiError(e).message;
  } finally {
    if (intCurrentRequest === intLoadRequest) boolLoading.value = false;
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

function closeDelete(): void {
  recipientDelete.value = null;
  strDeleteError.value = "";
  arrReference.value = [];
}

async function remove(): Promise<void> {
  if (!recipientDelete.value) return;
  boolBusy.value = true;
  strDeleteError.value = "";
  arrReference.value = [];
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
      Array.isArray(payload.error.references) &&
      payload.error.references.every(
        (reference: unknown): reference is RecipientReference => {
          if (!isRecord(reference) || typeof reference.name !== "string") return false;
          if (reference.kind === "job" || reference.kind === "delivery") return true;
          return (
            (reference.kind === "package" || reference.kind === "schedule") &&
            typeof reference.id === "string" &&
            typeof reference.department === "string"
          );
        },
      )
    )
      arrReference.value = payload.error.references;
  } finally {
    boolBusy.value = false;
  }
}

onMounted(() => void load());

onBeforeUnmount(() => {
  intLoadRequest += 1;
});
</script>

<style scoped></style>
