<!-- FileName: SharedFileUploadDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="660"
    aria-labelledby="file-upload-title">
    <v-card>
      <v-card-title id="file-upload-title">Upload File</v-card-title>

      <v-card-text>
        <v-form id="file-upload-form" validate-on="blur" @submit.prevent="submit">
          <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
            {{ error.message }}
            <p v-if="error.statusCode === 0 || error.code === 'invalid_response'">
              The upload result is not confirmed. Retry to continue the same upload.
            </p>
          </v-alert>

          <v-text-field
            :model-value="departmentPath"
            label="Department"
            variant="outlined"
            readonly />

          <v-file-input
            v-model="fileInput"
            label="File"
            variant="outlined"
            show-size
            :disabled="boolLocked"
            :rules="[validateFile]"
            @update:model-value="selectFile" />

          <p class="text-body-2 mb-4">
            {{ file ? formatFileSize(file.size) : "No file selected" }} · Maximum
            {{ formatFileSize(maxFileBytes) }} per file
          </p>

          <v-text-field
            v-model="strName"
            label="File Name"
            variant="outlined"
            :disabled="boolLocked"
            :rules="[validatePathName]" />

          <v-text-field :model-value="strPath" label="Path" variant="outlined" readonly />

          <v-switch
            v-model="boolOverwrite"
            label="Overwrite Existing File"
            color="primary"
            :disabled="boolLocked"
            hide-details
            class="mb-3" />

          <p v-if="boolOverwrite" class="text-body-2 mb-4">
            The existing file is replaced only after the complete upload is verified.
          </p>

          <template v-if="boolBusy">
            <p role="status" class="mb-2">
              {{ boolCancelRequested ? "Canceling upload…" : strStage }}
            </p>

            <v-progress-linear
              :model-value="floatProgress"
              :indeterminate="strStage !== 'Uploading…'"
              color="primary" />
          </template>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer />

        <v-btn :disabled="boolCancelRequested || boolCanceling" @click="cancel">
          {{ boolBusy ? "Cancel Upload" : "Cancel" }}
        </v-btn>

        <v-btn
          type="submit"
          form="file-upload-form"
          color="primary"
          variant="tonal"
          :loading="boolBusy"
          :disabled="boolBusy || boolCanceling || !boolAllowed">
          {{ upload ? "Retry Upload" : "Upload" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "@/stores/sessionStore";

import { formatFileSize } from "@/app/formatters";
import { validatePathName } from "@/app/validators";

import { ApiError, getApiError } from "@/api/errors";
import {
  getSha256,
  getOrCreateFileRequestIdentity,
  clearFileRequestIdentity,
  createSharedUpload,
  appendSharedChunk,
  finishSharedUpload,
} from "@/api/sharedFiles";
import type { FileInfoResponse, FileUploadResponse } from "@/api/generated/browserApi";

const props = defineProps<{ departmentPath: string; maxFileBytes: number }>();
const emit = defineEmits<{ close: []; saved: [file: FileInfoResponse] }>();
const sessionStore = useSessionStore();
const fileInput = shallowRef<File | File[] | null>(null);
const file = computed(() =>
  Array.isArray(fileInput.value) ? (fileInput.value[0] ?? null) : fileInput.value,
);
const strName = ref("");
const boolOverwrite = ref(false);
const upload = shallowRef<FileUploadResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const boolBusy = ref(false);
const boolCanceling = ref(false);
const boolCancelRequested = ref(false);
const strStage = ref("");
const floatProgress = ref(0);
const boolLocked = computed(
  () => boolBusy.value || boolCanceling.value || upload.value !== null,
);
const strPath = computed(() => `${props.departmentPath}/${strName.value}`);
const boolAllowed = computed(
  () =>
    sessionStore.access?.business_available &&
    sessionStore.access.departments.some(
      (department) => `/${department.path}` === props.departmentPath,
    ),
);
let identity: Awaited<ReturnType<typeof getOrCreateFileRequestIdentity>> | null = null;
let boolAlive = true;
function selectFile(): void {
  strName.value = file.value?.name ?? "";
  error.value = null;
}
function validateFile(): true | string {
  return !file.value
    ? "Select a file."
    : file.value.size > props.maxFileBytes
      ? `Select a file no larger than ${formatFileSize(props.maxFileBytes)}.`
      : true;
}
function handleUploadCompleted(result: FileUploadResponse): void {
  if (result.state !== "completed" || !result.file)
    throw new ApiError("The upload is not complete. Retry to check its status.");
  upload.value = result;
  if (identity) clearFileRequestIdentity(identity);
  if (boolAlive) emit("saved", result.file);
}
async function cancelKnownUpload(): Promise<void> {
  if (upload.value) {
    const result = await finishSharedUpload(upload.value.upload_id, "cancel");
    if (result.state === "completed") {
      handleUploadCompleted(result);
      return;
    }
    if (!["canceled", "expired", "failed"].includes(result.state))
      throw new ApiError("Cancellation is not confirmed. Try again.");
    if (identity) clearFileRequestIdentity(identity);
  }
  // An unknown create result keeps its identity for a later retry with the same file.
  if (boolAlive) emit("close");
}
async function cancel(): Promise<void> {
  if (boolBusy.value) {
    boolCancelRequested.value = true;
    return;
  }
  if (boolCanceling.value) return;
  boolCanceling.value = true;
  error.value = null;
  try {
    await cancelKnownUpload();
  } catch (e) {
    if (boolAlive) error.value = getApiError(e);
  } finally {
    if (boolAlive) boolCanceling.value = false;
  }
}
async function submit(event: SubmitEventPromise): Promise<void> {
  if (boolBusy.value || boolCanceling.value || !boolAllowed.value) return;
  boolBusy.value = true;
  boolCancelRequested.value = false;
  error.value = null;
  try {
    if (!(await event).valid || !file.value || !boolAlive) return;
    const source = file.value;
    strStage.value = "Checking file…";
    const body = {
      path: strPath.value,
      size_bytes: source.size,
      sha256: await getSha256(source),
      overwrite: boolOverwrite.value,
    };
    if (!boolAlive || boolCancelRequested.value) return;
    identity = await getOrCreateFileRequestIdentity(
      sessionStore.session!.user.id,
      "upload",
      body,
    );
    if (!boolAlive || boolCancelRequested.value) return;
    upload.value = await createSharedUpload({ ...body, request_id: identity.requestId });
    if (!boolAlive || boolCancelRequested.value) return;
    if (upload.value.state === "completed") {
      handleUploadCompleted(upload.value);
      return;
    }
    if (upload.value.state !== "receiving")
      throw new ApiError(
        "This upload is no longer available. Cancel and select the file again to start a new upload.",
      );
    strStage.value = "Uploading…";
    floatProgress.value = source.size ? (upload.value.offset / source.size) * 100 : 100;
    while (upload.value.offset < source.size) {
      const intOffset = upload.value.offset;
      const chunk = source.slice(intOffset, intOffset + upload.value.chunk_bytes);
      const result = await appendSharedChunk(upload.value.upload_id, intOffset, chunk);
      if (!boolAlive) return;
      if (
        result.upload_id !== upload.value.upload_id ||
        result.offset <= intOffset ||
        result.offset > source.size
      )
        throw new ApiError(
          "The service returned an unexpected upload offset. Retry to check this upload.",
          { code: "invalid_response" },
        );
      upload.value = result;
      floatProgress.value = (result.offset / source.size) * 100;
      if (boolCancelRequested.value) return;
    }
    strStage.value = "Verifying file…";
    handleUploadCompleted(await finishSharedUpload(upload.value.upload_id, "complete"));
  } catch (e) {
    if (boolAlive) error.value = getApiError(e);
  } finally {
    if (boolAlive && boolCancelRequested.value && upload.value?.state !== "completed") {
      try {
        await cancelKnownUpload();
      } catch (e) {
        error.value = getApiError(e);
      }
    }
    if (boolAlive) {
      boolBusy.value = false;
      boolCancelRequested.value = false;
    }
  }
}
onBeforeUnmount(() => {
  boolAlive = false;
});
</script>

<style scoped></style>
