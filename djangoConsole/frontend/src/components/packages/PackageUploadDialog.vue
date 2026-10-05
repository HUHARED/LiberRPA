<!-- FileName: PackageUploadDialog.vue -->
<template>
  <v-dialog :model-value="true" persistent max-width="680">
    <v-card>
      <v-card-title>Import Package</v-card-title>
      <v-card-text>
        <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
          {{ strError }}
        </v-alert>
        <v-select
          v-model="strDepartmentId"
          :items="arrDepartment"
          item-title="path"
          item-value="id"
          label="Department"
          :disabled="boolBusy || !!upload" />
        <v-file-input
          v-model="file"
          label="Package ZIP"
          accept=".zip,application/zip"
          show-size
          :disabled="boolBusy || !!upload" />
        <p class="text-body-2 text-medium-emphasis">
          Package metadata is checked before import. Existing packages cannot be
          overwritten.
        </p>
        <v-progress-linear
          v-if="upload"
          :model-value="upload.size_bytes ? (upload.offset / upload.size_bytes) * 100 : 0"
          height="12"
          class="my-4" />
        <p v-if="upload">
          {{ formatFileSize(upload.offset) }} / {{ formatFileSize(upload.size_bytes) }} ·
          {{ upload.state }}
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolBusy" @click="cancel">Cancel</v-btn>
        <v-btn
          color="primary"
          :loading="boolBusy"
          :disabled="!file || !strDepartmentId"
          @click="submit">
          {{ upload ? "Resume / Check" : "Import" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, ref, shallowRef } from "vue";
import { useSessionStore } from "@/stores/sessionStore";
import {
  createPackageUpload,
  getPackageUpload,
  appendPackageChunk,
  finishPackageUpload,
  type PackageUpload,
  type PackageInfo,
} from "@/api/packages";
import { getApiError } from "@/api/errors";
import { formatFileSize } from "@/app/formatters";
const emit = defineEmits<{ close: []; saved: [packageInfo: PackageInfo] }>();
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
const upload = shallowRef<PackageUpload | null>(null);
const strError = ref("");
const boolBusy = ref(false);
let strRequestId = crypto.randomUUID();
let strSubmittedIdentity = "";
async function cancel(): Promise<void> {
  boolBusy.value = true;
  try {
    if (upload.value && upload.value.state === "receiving")
      await finishPackageUpload(upload.value.upload_id, "cancel");
    emit("close");
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function submit(): Promise<void> {
  if (!file.value || !strDepartmentId.value) return;
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
    while (upload.value.state === "receiving" && upload.value.offset < file.value.size) {
      upload.value = await appendPackageChunk(
        upload.value.upload_id,
        upload.value.offset,
        file.value.slice(
          upload.value.offset,
          upload.value.offset + upload.value.chunk_bytes,
        ),
      );
    }
    if (upload.value.state === "receiving")
      upload.value = await finishPackageUpload(upload.value.upload_id, "complete");
    if (upload.value.package) emit("saved", upload.value.package);
    else
      strError.value = `The upload is ${upload.value.state}. Start a new import if this upload can no longer continue.`;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
</script>
<style scoped></style>
