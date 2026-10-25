<!-- FileName: RunEmailRecipientsView.vue -->
<template>
  <div class="d-flex align-center ga-3 mb-4">
    <h2 class="text-h6">Run Email Recipients</h2>
    <v-spacer />
    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolBusy || boolLoading"
      @click="load">
      Refresh
    </v-btn>

    <v-btn
      color="primary"
      variant="tonal"
      prepend-icon="mdi-plus"
      :disabled="boolBusy"
      @click="openForm(null)">
      Add Email
    </v-btn>
  </div>

  <v-alert
    v-if="strError"
    ref="pageErrorAlert"
    tabindex="-1"
    role="alert"
    type="error"
    variant="tonal"
    class="mb-4">
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
        :disabled="boolBusy"
        hide-details
        @update:model-value="load" />
    </v-col>
  </v-row>

  <v-data-table :headers="ARR_HEADER" :items="arrFiltered" :loading="boolLoading">
    <template #item.status="{ item }">
      <v-chip :color="DICT_STATUS_COLOR[item.status]" size="small" variant="tonal">
        {{ DICT_STATUS_LABEL[item.status] }}
      </v-chip>
    </template>

    <template #item.actions="{ item }">
      <div class="d-flex align-center ga-1">
        <v-btn
          v-tooltip:bottom="'Edit Notes'"
          size="small"
          variant="text"
          :disabled="boolBusy"
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
          :disabled="boolBusy"
          aria-label="Delete"
          icon="mdi-delete-outline"
          @click="openDelete(item)" />
      </div>
    </template>
  </v-data-table>

  <v-dialog
    :model-value="boolForm"
    :persistent="boolBusy"
    max-width="640"
    @update:model-value="!$event && closeForm()">
    <v-card v-if="boolForm" ref="feedbackContainer">
      <v-card-title>{{ recipientEdit ? "Edit Notes" : "Add Email" }}</v-card-title>

      <v-card-text>
        <v-form id="run-email-recipient-form" validate-on="submit" @submit.prevent="save">
          <v-alert
            v-if="formError"
            ref="errorAlert"
            tabindex="-1"
            type="error"
            variant="tonal"
            class="mb-4"
            role="alert">
            {{ formError.message }}
            <p
              v-for="strMessage in formError.fields.__all__"
              :key="strMessage"
              class="mt-2">
              {{ strMessage }}
            </p>
          </v-alert>

          <v-text-field
            v-model="strEmail"
            :variant="recipientEdit ? 'plain' : 'outlined'"
            label="Email"
            type="email"
            :readonly="!!recipientEdit"
            :rules="[validateEmail]"
            :error-messages="formError?.fields.email ?? []"
            :disabled="boolBusy"
            required
            @update:model-value="formError = null" />

          <v-textarea
            v-model="strNotes"
            variant="outlined"
            label="Notes (optional)"
            rows="3"
            counter="2000"
            :counter-value="(value) => Array.from(value ?? '').length"
            :rules="[validateNotes]"
            :error-messages="formError?.fields.notes ?? []"
            :disabled="boolBusy"
            @update:model-value="formError = null" />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="closeForm">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          type="submit"
          form="run-email-recipient-form"
          variant="tonal"
          :prepend-icon="recipientEdit ? 'mdi-content-save-outline' : 'mdi-plus'"
          color="primary"
          :loading="boolBusy"
          :disabled="boolBusy || !strEmail?.trim()">
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
    <v-card ref="deleteFeedbackContainer">
      <v-card-title>Delete Email</v-card-title>

      <v-card-text>
        <p class="text-anywhere">
          Delete
          <span class="text-highlight font-weight-bold">{{ recipientDelete?.email }}?</span>
          Remove this address from packages and schedules first. Wait for active Jobs and
          pending Run email deliveries using this address to finish. Verification links will
          stop working.
        </p>

        <v-alert
          v-if="strDeleteError"
          ref="deleteErrorAlert"
          tabindex="-1"
          role="alert"
          type="error"
          variant="tonal"
          class="mt-4">
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
          :disabled="boolBusy"
          @click="remove">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { SubmitEventPromise } from "vuetify";

import {
  getRunEmailRecipients,
  saveRunEmailRecipient,
  actOnRunEmailRecipient,
  type RunEmailRecipientFilter,
  type RunEmailRecipient,
} from "@/api/runEmail";
import { RunEmailRecipientStatus } from "@/api/generated/browserApi";
import { type ApiError, getApiError } from "@/api/errors";
import { isRecord } from "@/api/responses";

type RecipientReference =
  | {
      kind: "package" | "schedule";
      id: string;
      name: string;
      department: string;
    }
  | { kind: "job" | "delivery"; name: string };

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);
const deleteFeedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const deleteErrorAlert = ref<{ $el: HTMLElement } | null>(null);
const pageErrorAlert = ref<{ $el: HTMLElement } | null>(null);

const DICT_STATUS_LABEL: Record<RunEmailRecipientStatus, string> = {
  [RunEmailRecipientStatus.Member]: "Member",
  [RunEmailRecipientStatus.Verified]: "Verified",
  [RunEmailRecipientStatus.Pending]: "Pending",
};
const DICT_STATUS_COLOR: Record<RunEmailRecipientStatus, string> = {
  [RunEmailRecipientStatus.Member]: "info",
  [RunEmailRecipientStatus.Verified]: "success",
  [RunEmailRecipientStatus.Pending]: "warning",
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

const arrRecipient = ref<RunEmailRecipient[]>([]);
const strSearch = ref("");
const strStatus = ref<RunEmailRecipientFilter>("all");
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolForm = ref(false);
const recipientEdit = ref<RunEmailRecipient | null>(null);
const recipientDelete = ref<RunEmailRecipient | null>(null);
const strEmail = ref<string | null>("");
const strNotes = ref<string | null>("");
const strError = ref("");
const formError = shallowRef<ApiError | null>(null);
const strDeleteError = ref("");
const strSuccess = ref("");
const arrReference = ref<RecipientReference[]>([]);
let intLoadRequest = 0;
let boolUnmounted = false;

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
  if (boolUnmounted) return;
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

function validateEmail(value: string | null): true | string {
  const strValue = value?.trim() ?? "";
  if (!strValue) return "Enter an email address.";
  return Array.from(strValue).length <= 254 ? true : "Use at most 254 characters.";
}

function validateNotes(value: string | null): true | string {
  return Array.from(value ?? "").length <= 2000 ? true : "Use at most 2000 characters.";
}

function openForm(recipient: RunEmailRecipient | null): void {
  if (boolUnmounted || boolBusy.value || boolForm.value || recipientDelete.value) return;
  recipientEdit.value = recipient;
  strEmail.value = recipient?.email ?? "";
  strNotes.value = recipient?.notes ?? "";
  formError.value = null;
  strSuccess.value = "";
  boolForm.value = true;
}

function closeForm(): void {
  if (boolBusy.value) return;
  boolForm.value = false;
  recipientEdit.value = null;
  strEmail.value = "";
  strNotes.value = "";
  formError.value = null;
}

async function save(event: SubmitEventPromise): Promise<void> {
  if (boolUnmounted || boolBusy.value || !boolForm.value || !strEmail.value?.trim()) return;
  const strRecipientId = recipientEdit.value?.id ?? null;
  const strSubmittedEmail = strEmail.value?.trim() ?? "";
  const strSubmittedNotes = strNotes.value ?? "";
  let boolShowFeedback = false;
  boolBusy.value = true;
  formError.value = null;
  strSuccess.value = "";
  try {
    const validation = await event;
    if (!validation.valid) {
      boolShowFeedback = true;
      return;
    }
    if (boolUnmounted) return;

    await saveRunEmailRecipient(strRecipientId, strSubmittedEmail, strSubmittedNotes);
    if (boolUnmounted) return;
    boolForm.value = false;
    strSuccess.value = strRecipientId
      ? "Notes saved."
      : "Address added. Ask the recipient to confirm the verification email.";
    await load();
  } catch (e) {
    if (!boolUnmounted) {
      formError.value = getApiError(e);
      boolShowFeedback = true;
    }
  } finally {
    boolBusy.value = false;
    if (boolShowFeedback && !boolUnmounted) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

async function resend(id: string): Promise<void> {
  if (boolUnmounted || boolBusy.value || boolForm.value || recipientDelete.value) return;
  boolBusy.value = true;
  strError.value = "";
  strSuccess.value = "";
  try {
    await actOnRunEmailRecipient(id, "resend");
    if (!boolUnmounted) strSuccess.value = "Verification email requested.";
  } catch (e) {
    if (!boolUnmounted) strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
    if (strError.value && !boolUnmounted) {
      await nextTick();
      revealFormFeedback(pageErrorAlert.value?.$el, pageErrorAlert.value?.$el, true);
    }
  }
}

function openDelete(recipient: RunEmailRecipient): void {
  if (boolUnmounted || boolBusy.value || boolForm.value || recipientDelete.value) return;
  recipientDelete.value = recipient;
  strDeleteError.value = "";
  arrReference.value = [];
  strSuccess.value = "";
}

function closeDelete(): void {
  if (boolBusy.value) return;
  recipientDelete.value = null;
  strDeleteError.value = "";
  arrReference.value = [];
}

async function remove(): Promise<void> {
  if (boolUnmounted || boolBusy.value || !recipientDelete.value) return;
  const strRecipientId = recipientDelete.value.id;
  boolBusy.value = true;
  strDeleteError.value = "";
  arrReference.value = [];
  strSuccess.value = "";
  try {
    await actOnRunEmailRecipient(strRecipientId, "delete");
    if (boolUnmounted) return;
    recipientDelete.value = null;
    strSuccess.value = "Email address deleted.";
    await load();
  } catch (e) {
    if (boolUnmounted) return;
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
    if (strDeleteError.value && !boolUnmounted) {
      await nextTick();
      revealFormFeedback(deleteFeedbackContainer.value?.$el, deleteErrorAlert.value?.$el);
    }
  }
}

onMounted(() => void load());

onBeforeUnmount(() => {
  boolUnmounted = true;
  intLoadRequest += 1;
});
</script>

<style scoped></style>
