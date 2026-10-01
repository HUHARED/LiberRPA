<!-- FileName: QueueUploadDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="820"
    aria-labelledby="queue-upload-title">
    <v-card>
      <v-card-title id="queue-upload-title">Upload Items</v-card-title>
      <v-card-text>
        <v-text-field :model-value="queue.path" label="Queue" variant="outlined" readonly />
        <v-file-input
          label="File"
          accept=".xlsx,.xls,.csv,.tsv,.txt,.json,.jsonl"
          variant="outlined"
          :disabled="saving || reading"
          :loading="reading"
          @update:model-value="selectFile" />
        <v-alert v-if="fileError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ fileError }}
        </v-alert>
        <template v-if="source">
          <v-select
            v-if="source.excel"
            v-model="worksheet"
            :items="source.workbook?.SheetNames ?? []"
            label="Worksheet"
            variant="outlined"
            :disabled="saving" />
          <template v-if="source.kind === 'table'">
            <v-switch
              v-model="header"
              label="First Row Is Header"
              color="primary"
              :disabled="saving" />
            <v-select
              v-model="column"
              :items="columns"
              label="Column"
              variant="outlined"
              :disabled="saving" />
          </template>
          <v-select
            v-if="source.kind === 'table' || source.kind === 'txt'"
            v-model="format"
            :items="[
              { title: 'Text', value: 'text' },
              { title: 'JSON', value: 'json' },
            ]"
            label="Value Format"
            variant="outlined"
            :disabled="saving" />
          <v-alert v-if="preview.error" type="info" variant="tonal" class="mb-4">
            {{ preview.error }}
          </v-alert>
          <template v-else>
            <p class="mb-3">
              {{ preview.rows.length }} items · {{ preview.skipped }} empty entries skipped
            </p>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Preview (first 10 items)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in preview.rows.slice(0, 10)" :key="row.source">
                  <td>{{ row.source }}</td>
                  <td class="table-text">
                    {{ JSON.stringify(row.value).slice(0, 160) }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </template>
        <v-alert v-if="error" type="error" variant="tonal" class="mt-4" role="alert">
          Upload was not confirmed. {{ error.message }}
          <p v-for="message in Object.values(error.fields).flat()" :key="message">
            {{ message }}
          </p>
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="saving" @click="emit('close')">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="tonal"
          :loading="saving"
          :disabled="saving || reading || !!preview.error || !source"
          @click="submit">
          Upload
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import { useSessionStore } from "../stores/sessionStore";

import { type ApiError, getApiError } from "../api/errors";
import { changeQueueItems } from "../api/dataQueues";
import type {
  QueueEntryResponse,
  QueueMutationResponse,
} from "../api/generated/browserApi";
import {
  readQueueFile,
  getQueueColumns,
  convertQueueFile,
  type QueueImportSource,
} from "../app/queueImport";

const props = defineProps<{ queue: QueueEntryResponse }>();
const emit = defineEmits<{ close: []; uploaded: [result: QueueMutationResponse] }>();
const session = useSessionStore();
const source = shallowRef<QueueImportSource | null>(null);
const worksheet = ref("");
const column = ref<number | null>(null);
const header = ref(false);
const format = ref<"text" | "json">("text");
const fileError = ref("");
const error = shallowRef<ApiError | null>(null);
const reading = ref(false);
const saving = ref(false);
let revision = 0;
const columns = computed(() => {
  try {
    return source.value ? getQueueColumns(source.value, worksheet.value, header.value) : [];
  } catch {
    return [];
  }
});
const preview = computed(() => {
  try {
    if (!source.value) throw new Error("Choose a file.");
    return {
      ...convertQueueFile(source.value, {
        worksheet: worksheet.value,
        column: column.value,
        header: header.value,
        format: format.value,
      }),
      error: "",
    };
  } catch (e) {
    return {
      rows: [],
      skipped: 0,
      error: e instanceof Error ? e.message : "The file could not be converted.",
    };
  }
});
watch(worksheet, () => {
  column.value = columns.value.length === 1 ? columns.value[0]!.value : null;
});
async function selectFile(value: File | File[] | null): Promise<void> {
  const current = ++revision;
  source.value = null;
  fileError.value = "";
  error.value = null;
  column.value = null;
  worksheet.value = "";
  const file = Array.isArray(value) ? value[0] : value;
  if (!file) return;
  reading.value = true;
  try {
    const result = await readQueueFile(file);
    if (current !== revision) return;
    source.value = result;
    worksheet.value =
      result.workbook?.SheetNames.length === 1 ? result.workbook.SheetNames[0]! : "";
  } catch (e) {
    if (current === revision)
      fileError.value = e instanceof Error ? e.message : "The file could not be read.";
  } finally {
    if (current === revision) reading.value = false;
  }
}
async function submit(): Promise<void> {
  if (saving.value || reading.value || preview.value.error || !session.session) return;
  const current = revision;
  saving.value = true;
  error.value = null;
  try {
    const result = await changeQueueItems(
      session.session.user.id,
      props.queue.id,
      "upload",
      { items: preview.value.rows.map((row) => row.value) },
    );
    if (current === revision) emit("uploaded", result);
  } catch (e) {
    if (current === revision) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await session.refreshSession();
    }
  } finally {
    saving.value = false;
  }
}
onBeforeUnmount(() => {
  revision += 1;
});
</script>

<style scoped></style>
