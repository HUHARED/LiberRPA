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
            :disabled="locked"
            :rules="[fileRule]"
            @update:model-value="selectFile" />
          <p class="text-body-2 mb-4">
            {{ file ? formatFileSize(file.size) : "No file selected" }} · Maximum
            {{ formatFileSize(maxFileBytes) }} per file
          </p>
          <v-text-field
            v-model="name"
            label="File Name"
            variant="outlined"
            :disabled="locked"
            :rules="[validatePathName]" />
          <v-text-field :model-value="path" label="Path" variant="outlined" readonly />
          <v-switch
            v-model="overwrite"
            label="Overwrite Existing File"
            color="primary"
            :disabled="locked"
            hide-details
            class="mb-3" />
          <p v-if="overwrite" class="text-body-2 mb-4">
            The existing file is replaced only after the complete upload is verified.
          </p>
          <template v-if="busy">
            <p role="status" class="mb-2">
              {{ cancelRequested ? "Canceling upload…" : stage }}
            </p>
            <v-progress-linear
              :model-value="progress"
              :indeterminate="stage !== 'Uploading…'"
              color="primary" />
          </template>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="cancelRequested || canceling" @click="cancel">
          {{ busy ? "Cancel Upload" : "Cancel" }}
        </v-btn>
        <v-btn
          type="submit"
          form="file-upload-form"
          color="primary"
          variant="tonal"
          :loading="busy"
          :disabled="busy || canceling || !allowed">
          {{ upload ? "Retry Upload" : "Upload" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef } from "vue";
import type { SubmitEventPromise } from "vuetify";

import { useSessionStore } from "../stores/sessionStore";

import { formatFileSize } from "../app/formatters";
import { validatePathName } from "../app/validators";

import { ApiError, getApiError } from "../api/errors";
import {
  getSha256,
  getOrCreateFileRequestIdentity,
  clearFileRequestIdentity,
  createSharedUpload,
  appendSharedChunk,
  finishSharedUpload,
} from "../api/sharedFiles";
import type { FileInfoResponse, FileUploadResponse } from "../api/generated/browserApi";

const props = defineProps<{ departmentPath: string; maxFileBytes: number }>();
const emit = defineEmits<{ close: []; saved: [file: FileInfoResponse] }>();
const session = useSessionStore();
const fileInput = shallowRef<File | File[] | null>(null);
const file = computed(() =>
  Array.isArray(fileInput.value) ? (fileInput.value[0] ?? null) : fileInput.value,
);
const name = ref("");
const overwrite = ref(false);
const upload = shallowRef<FileUploadResponse | null>(null);
const error = shallowRef<ApiError | null>(null);
const busy = ref(false);
const canceling = ref(false);
const cancelRequested = ref(false);
const stage = ref("");
const progress = ref(0);
const locked = computed(() => busy.value || canceling.value || upload.value !== null);
const path = computed(() => `${props.departmentPath}/${name.value}`);
const allowed = computed(
  () =>
    session.access?.business_available &&
    session.access.departments.some(
      (department) => `/${department.path}` === props.departmentPath,
    ),
);
let identity: Awaited<ReturnType<typeof getOrCreateFileRequestIdentity>> | null = null;
let alive = true;
function selectFile(): void {
  name.value = file.value?.name ?? "";
  error.value = null;
}
function fileRule(): true | string {
  return !file.value
    ? "Select a file."
    : file.value.size > props.maxFileBytes
      ? `Select a file no larger than ${formatFileSize(props.maxFileBytes)}.`
      : true;
}
function saved(result: FileUploadResponse): void {
  if (result.state !== "completed" || !result.file)
    throw new ApiError("The upload is not complete. Retry to check its status.");
  upload.value = result;
  if (identity) clearFileRequestIdentity(identity);
  if (alive) emit("saved", result.file);
}
async function cancelKnownUpload(): Promise<void> {
  if (upload.value) {
    const result = await finishSharedUpload(upload.value.upload_id, "cancel");
    if (result.state === "completed") {
      saved(result);
      return;
    }
    if (!["canceled", "expired", "failed"].includes(result.state))
      throw new ApiError("Cancellation is not confirmed. Try again.");
    if (identity) clearFileRequestIdentity(identity);
  }
  // An unknown create result keeps its identity for a later retry with the same file.
  if (alive) emit("close");
}
async function cancel(): Promise<void> {
  if (busy.value) {
    cancelRequested.value = true;
    return;
  }
  if (canceling.value) return;
  canceling.value = true;
  error.value = null;
  try {
    await cancelKnownUpload();
  } catch (e) {
    if (alive) error.value = getApiError(e);
  } finally {
    if (alive) canceling.value = false;
  }
}
async function submit(event: SubmitEventPromise): Promise<void> {
  if (busy.value || canceling.value || !allowed.value) return;
  busy.value = true;
  cancelRequested.value = false;
  error.value = null;
  try {
    if (!(await event).valid || !file.value || !alive) return;
    const source = file.value;
    stage.value = "Checking file…";
    const body = {
      path: path.value,
      size_bytes: source.size,
      sha256: await getSha256(source),
      overwrite: overwrite.value,
    };
    if (!alive || cancelRequested.value) return;
    identity = await getOrCreateFileRequestIdentity(
      session.session!.user.id,
      "upload",
      body,
    );
    if (!alive || cancelRequested.value) return;
    upload.value = await createSharedUpload({ ...body, request_id: identity.requestId });
    if (!alive || cancelRequested.value) return;
    if (upload.value.state === "completed") {
      saved(upload.value);
      return;
    }
    if (upload.value.state !== "receiving")
      throw new ApiError(
        "This upload is no longer available. Cancel and select the file again to start a new upload.",
      );
    stage.value = "Uploading…";
    progress.value = source.size ? (upload.value.offset / source.size) * 100 : 100;
    while (upload.value.offset < source.size) {
      const offset = upload.value.offset;
      const chunk = source.slice(offset, offset + upload.value.chunk_bytes);
      const result = await appendSharedChunk(upload.value.upload_id, offset, chunk);
      if (!alive) return;
      if (
        result.upload_id !== upload.value.upload_id ||
        result.offset <= offset ||
        result.offset > source.size
      )
        throw new ApiError(
          "The service returned an unexpected upload offset. Retry to check this upload.",
          { code: "invalid_response" },
        );
      upload.value = result;
      progress.value = (result.offset / source.size) * 100;
      if (cancelRequested.value) return;
    }
    stage.value = "Verifying file…";
    saved(await finishSharedUpload(upload.value.upload_id, "complete"));
  } catch (e) {
    if (alive) error.value = getApiError(e);
  } finally {
    if (alive && cancelRequested.value && upload.value?.state !== "completed") {
      try {
        await cancelKnownUpload();
      } catch (e) {
        error.value = getApiError(e);
      }
    }
    if (alive) {
      busy.value = false;
      cancelRequested.value = false;
    }
  }
}
onBeforeUnmount(() => {
  alive = false;
});
</script>

<style scoped></style>
