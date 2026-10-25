<!-- FileName: PackageUploadDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolBusy"
    max-width="680"
    @update:model-value="!$event && cancel()">
    <v-card ref="feedbackContainer">
      <v-card-title>Upload Package</v-card-title>

      <v-card-text>
        <v-alert
          v-if="strError"
          ref="errorAlert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert">
          {{ strError }}
        </v-alert>

        <v-select
          v-model="strDepartmentId"
          variant="outlined"
          :items="arrDepartment"
          item-title="path"
          item-value="id"
          label="Department"
          :disabled="boolBusy || !!upload" />

        <v-file-input
          v-model="file"
          variant="outlined"
          label="Package ZIP"
          accept=".zip,application/zip"
          show-size
          :disabled="boolBusy || !!upload" />

        <p class="text-body-2 text-medium-emphasis">
          Existing package versions cannot be overwritten.
        </p>

        <v-progress-linear
          v-if="upload"
          :model-value="upload.size_bytes ? (upload.offset / upload.size_bytes) * 100 : 0"
          height="12"
          class="my-4" />

        <p v-if="upload">
          {{ formatFileSize(upload.offset) }} / {{ formatFileSize(upload.size_bytes) }} ·
          {{ PACKAGE_UPLOAD_LABELS[upload.state] }}
        </p>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="cancel">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          :prepend-icon="upload ? 'mdi-refresh' : 'mdi-upload'"
          color="primary"
          :loading="boolBusy"
          :disabled="boolBusy || !file || !strDepartmentId"
          @click="submit">
          {{ upload ? "Resume / Check" : "Upload" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { nextTick, computed, ref, shallowRef } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import {
  createPackageUpload,
  getPackageUpload,
  appendPackageChunk,
  finishPackageUpload,
} from "@/api/packages";
import { getApiError } from "@/api/errors";
import {
  type PackageResponse,
  type PackageUploadResponse,
  PackageUploadState,
} from "@/api/generated/browserApi";

import { formatFileSize } from "@/app/formatters";
import { PACKAGE_UPLOAD_LABELS } from "@/app/runLabels";

import { revealFormFeedback } from "@/app/formFeedback";

const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);

const emit = defineEmits<{ close: []; saved: [packageInfo: PackageResponse] }>();
const sessionStore = useSessionStore();

const arrDepartment = computed(
  () =>
    sessionStore.access?.departments.filter(
      (department) => sessionStore.access?.is_org_admin || department.role === "developer",
    ) ?? [],
);

const strDepartmentId = ref(
  arrDepartment.value.length === 1 ? arrDepartment.value[0]!.id : "",
);

const file = ref<File | null>(null);
const upload = shallowRef<PackageUploadResponse | null>(null);
const strError = ref("");
const boolBusy = ref(false);
let strRequestId = crypto.randomUUID();
let strSubmittedIdentity = "";

async function cancel(): Promise<void> {
  if (boolBusy.value) return;
  strError.value = "";
  boolBusy.value = true;
  try {
    if (upload.value && upload.value.state === PackageUploadState.Receiving)
      await finishPackageUpload(upload.value.upload_id, "cancel");
    emit("close");
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
    if (strError.value) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}

async function submit(): Promise<void> {
  if (boolBusy.value || !file.value || !strDepartmentId.value) return;
  const strIdentity = JSON.stringify([
    strDepartmentId.value,
    file.value.name,
    file.value.size,
    file.value.lastModified,
  ]);
  if (strSubmittedIdentity && strSubmittedIdentity !== strIdentity)
    strRequestId = crypto.randomUUID();
  strSubmittedIdentity = strIdentity;
  boolBusy.value = true;
  strError.value = "";
  try {
    upload.value = upload.value
      ? await getPackageUpload(upload.value.upload_id)
      : await createPackageUpload(file.value, strDepartmentId.value, strRequestId);
    while (
      upload.value.state === PackageUploadState.Receiving &&
      upload.value.offset < file.value.size
    ) {
      upload.value = await appendPackageChunk(
        upload.value.upload_id,
        upload.value.offset,
        file.value.slice(
          upload.value.offset,
          upload.value.offset + upload.value.chunk_bytes,
        ),
      );
    }
    if (upload.value.state === PackageUploadState.Receiving)
      upload.value = await finishPackageUpload(upload.value.upload_id, "complete");
    if (upload.value.package) emit("saved", upload.value.package);
    else
      strError.value =
        `Upload status: ${PACKAGE_UPLOAD_LABELS[upload.value.state]}. ` +
        "Start a new import.";
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
    if (strError.value) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
  }
}
</script>

<style scoped></style>
