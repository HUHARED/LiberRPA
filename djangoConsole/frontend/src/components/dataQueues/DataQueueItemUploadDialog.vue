<!-- FileName: DataQueueItemUploadDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolSaving"
    scrollable
    max-width="820"
    aria-labelledby="queue-upload-title"
    @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title id="queue-upload-title">Upload Items</v-card-title>

      <v-card-text>
        <v-text-field :model-value="queue.path" label="Queue" variant="plain" readonly />

        <v-file-input
          label="File"
          accept=".xlsx,.xls,.csv,.tsv,.txt,.json,.jsonl"
          variant="outlined"
          :disabled="boolSaving || boolReading"
          :loading="boolReading"
          @update:model-value="selectFile" />

        <v-alert v-if="strFileError" type="error" variant="tonal" class="mb-4" role="alert">
          {{ strFileError }}
        </v-alert>

        <template v-if="source">
          <v-select
            v-if="source.excel"
            v-model="strWorksheetName"
            :items="source.workbook?.SheetNames ?? []"
            label="Worksheet"
            variant="outlined"
            :disabled="boolSaving" />

          <template v-if="source.kind === 'table'">
            <v-switch
              v-model="boolHasHeader"
              label="First Row Is Header"
              color="primary"
              :disabled="boolSaving" />

            <v-select
              v-model="intColumnIndex"
              :items="columns"
              label="Column"
              variant="outlined"
              :disabled="boolSaving" />
          </template>

          <v-select
            v-if="source.kind === 'table' || source.kind === 'txt'"
            v-model="strFormat"
            :items="[
              { title: 'Text', value: 'text' },
              { title: 'JSON', value: 'json' },
            ]"
            label="Value Format"
            variant="outlined"
            :disabled="boolSaving" />

          <v-alert v-if="preview.error" type="info" variant="tonal" class="mb-4">
            {{ preview.error }}
          </v-alert>

          <template v-else>
            <p class="mb-3">
              <span class="font-weight-bold">{{ preview.rows.length }}</span>
              items ·
              <span class="font-weight-bold">{{ preview.skipped }}</span>
              empty entries skipped
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
          <p v-for="strMessage in Object.values(error.fields).flat()" :key="strMessage">
            {{ strMessage }}
          </p>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="emit('close')">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-upload"
          :loading="boolSaving"
          :disabled="boolSaving || boolReading || !!preview.error || !source"
          @click="submit">
          Upload
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { changeQueueItems } from "@/api/dataQueues";
import type { QueueEntryResponse, QueueMutationResponse } from "@/api/generated/browserApi";

import {
  readQueueFile,
  getQueueColumns,
  convertQueueFile,
  type QueueImportSource,
} from "@/app/queueImport";

const props = defineProps<{ queue: QueueEntryResponse }>();
const emit = defineEmits<{ close: []; uploaded: [result: QueueMutationResponse] }>();
const sessionStore = useSessionStore();
const source = shallowRef<QueueImportSource | null>(null);
const strWorksheetName = ref("");
const intColumnIndex = ref<number | null>(null);
const boolHasHeader = ref(false);
const strFormat = ref<"text" | "json">("text");
const strFileError = ref("");
const error = shallowRef<ApiError | null>(null);
const boolReading = ref(false);
const boolSaving = ref(false);
let intRevision = 0;

const columns = computed(() => {
  try {
    return source.value
      ? getQueueColumns(source.value, strWorksheetName.value, boolHasHeader.value)
      : [];
  } catch {
    return [];
  }
});

const preview = computed(() => {
  try {
    if (!source.value) throw new Error("Choose a file.");
    return {
      ...convertQueueFile(source.value, {
        worksheet: strWorksheetName.value,
        column: intColumnIndex.value,
        header: boolHasHeader.value,
        format: strFormat.value,
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

watch(strWorksheetName, () => {
  intColumnIndex.value = columns.value.length === 1 ? columns.value[0]!.value : null;
});

async function selectFile(value: File | File[] | null): Promise<void> {
  const intCurrentRevision = ++intRevision;
  source.value = null;
  strFileError.value = "";
  error.value = null;
  intColumnIndex.value = null;
  strWorksheetName.value = "";
  const file = Array.isArray(value) ? value[0] : value;
  if (!file) return;
  boolReading.value = true;
  try {
    const result = await readQueueFile(file);
    if (intCurrentRevision !== intRevision) return;
    source.value = result;
    strWorksheetName.value =
      result.workbook?.SheetNames.length === 1 ? result.workbook.SheetNames[0]! : "";
  } catch (e) {
    if (intCurrentRevision === intRevision)
      strFileError.value = e instanceof Error ? e.message : "The file could not be read.";
  } finally {
    if (intCurrentRevision === intRevision) boolReading.value = false;
  }
}

async function submit(): Promise<void> {
  if (boolSaving.value || boolReading.value || preview.value.error || !sessionStore.session)
    return;
  const intCurrentRevision = intRevision;
  boolSaving.value = true;
  error.value = null;
  try {
    const result = await changeQueueItems(
      sessionStore.session.user.id,
      props.queue.id,
      "upload",
      { items: preview.value.rows.map((row) => row.value) },
    );
    if (intCurrentRevision === intRevision) emit("uploaded", result);
  } catch (e) {
    if (intCurrentRevision === intRevision) {
      error.value = getApiError(e);
      if (error.value.statusCode === 403) await sessionStore.refreshSession();
    }
  } finally {
    boolSaving.value = false;
  }
}

onBeforeUnmount(() => {
  intRevision += 1;
});
</script>

<style scoped></style>
