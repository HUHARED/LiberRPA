<!-- FileName: RunLogs.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <v-switch
      v-model="boolFollow"
      label="Follow Latest"
      hide-details
      density="compact"
      @update:model-value="resumeFollow" />
    <v-spacer />
    <v-btn variant="tonal" :loading="boolLoading" @click="refresh">Refresh</v-btn>
    <v-btn variant="tonal" :disabled="!downloadEnabled" @click="emit('download')">
      Download Logs
    </v-btn>
  </div>
  <p class="text-caption mb-3">{{ downloadReason }}</p>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
    {{ strError }}
  </v-alert>
  <v-alert v-if="boolCleared" type="info" variant="tonal" class="mb-3">
    Logs for this Run were cleared from Console.
  </v-alert>
  <v-row>
    <v-col cols="12" md="4">
      <v-select
        v-model="strProcess"
        :items="[
          { title: 'All Processes', value: '' },
          ...arrProcess.map((name) => ({ title: name, value: name })),
        ]"
        label="Process"
        hide-details
        @update:model-value="intPage = 1" />
    </v-col>
    <v-col cols="12" md="4">
      <v-select
        v-model="arrLevel"
        :items="ARR_LOG_LEVEL"
        label="Level"
        multiple
        chips
        hide-details
        @update:model-value="intPage = 1" />
    </v-col>
    <v-col cols="12" md="4">
      <v-text-field
        v-model="strMessage"
        label="Message"
        hide-details
        @update:model-value="intPage = 1" />
    </v-col>
  </v-row>
  <p class="text-body-2 text-medium-emphasis my-3">
    Filters apply to loaded logs. {{ arrLog.length }} loaded entries ·
    {{ formatFileSize(intLoadedBytes) }} · Time zone: {{ timeZone }}
  </p>
  <v-data-table
    v-model:expanded="arrExpanded"
    v-model:page="intPage"
    :headers="ARR_HEADER"
    :items="arrFiltered"
    :items-per-page="200"
    :items-per-page-options="[200]"
    item-value="log_id"
    show-expand
    disable-sort
    @update:expanded="pauseFollow"
    @update:page="pauseFollow">
    <template #item.timestamp="{ item }">
      {{ formatDateTime(item.timestamp, timeZone) }}
    </template>
    <template #item.level="{ item }">{{ item.level }}</template>
    <template #item.process="{ item }">{{ item.process_name || "—" }}</template>
    <template #item.message_text="{ item }">
      <div class="text-truncate">{{ item.message_text }}</div>
    </template>
    <template #expanded-row="{ item, columns }">
      <tr>
        <td :colspan="columns.length">
          <h3 class="text-subtitle-1 my-2">Message</h3>
          <pre class="text-pre-wrap text-break mb-4">{{ item.message_text }}</pre>
          <h3 class="text-subtitle-1 my-2">Fields</h3>
          <v-table density="compact" class="mb-4">
            <tbody>
              <tr v-for="(value, key) in getFields(item)" :key="key">
                <td>{{ key }}</td>
                <td>
                  <pre class="text-pre-wrap text-break">{{ value }}</pre>
                </td>
              </tr>
            </tbody>
          </v-table>
        </td>
      </tr>
    </template>
    <template #no-data>
      {{ boolLoading ? "Loading logs…" : "No loaded logs match the filters." }}
    </template>
  </v-data-table>
  <div class="d-flex align-center flex-wrap ga-3 mt-3">
    <v-btn
      :disabled="!boolHasMore || boolLimit || boolLoading"
      :loading="boolLoading"
      variant="tonal"
      @click="loadOlder">
      Load Older
    </v-btn>
    <span v-if="boolLimit" class="text-body-2">
      Preview window limit reached (10,000 entries / 10 MiB).
    </span>
    <span v-else-if="!boolHasMore" class="text-body-2">No older logs available.</span>
    <span v-if="!boolComplete" class="text-body-2 text-medium-emphasis">
      More logs may still arrive from the Executor.
    </span>
  </div>
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref } from "vue";
import { getRunLogs, type LogEntry } from "@/api/runs";
import { ARR_LOG_LEVEL, type LogLevel } from "@/api/runOptions";
import { getApiError } from "@/api/errors";
import { formatDateTime, formatFileSize, formatJsonValue } from "@/app/formatters";
const props = defineProps<{
  runId: string;
  running: boolean;
  timeZone: string;
  active: boolean;
  downloadEnabled: boolean;
  downloadReason: string;
}>();
const emit = defineEmits<{ download: [] }>();
const ARR_HEADER = [
  { title: "Timestamp", key: "timestamp", width: 235 },
  { title: "Level", key: "level", width: 95 },
  { title: "Process", key: "process", width: 180 },
  { title: "Message", key: "message_text", maxWidth: 600 },
];
const INT_MAX_ENTRIES = 10000;
const INT_MAX_BYTES = 10 * 1024 * 1024;
const arrLog = shallowRef<LogEntry[]>([]);
const arrExpanded = ref<string[]>([]);
const arrLevel = ref<LogLevel[]>([]);
const strProcess = ref("");
const strMessage = ref("");
const intPage = ref(1);
const boolFollow = ref(props.running);
const boolLoading = ref(false);
const strError = ref("");
const boolHasMore = ref(false);
const boolCleared = ref(false);
const boolComplete = ref(false);
const boolLimit = ref(false);
const intLoadedBytes = ref(0);
let intAfter = 0;
let intBefore: number | null = null;
let timer: ReturnType<typeof setInterval> | undefined;
const arrProcess = computed(() =>
  [...new Set(arrLog.value.map((log) => log.process_name))].filter(Boolean).sort(),
);
const arrFiltered = computed(() =>
  arrLog.value
    .filter(
      (log) =>
        (!strProcess.value || log.process_name === strProcess.value) &&
        (!arrLevel.value.length || arrLevel.value.some((level) => level === log.level)) &&
        (!strMessage.value ||
          log.message_text
            .toLocaleLowerCase()
            .includes(strMessage.value.toLocaleLowerCase())),
    )
    .sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) || right.sequence - left.sequence,
    ),
);
function getFields(log: LogEntry): Record<string, string> {
  return {
    user_name: formatJsonValue(log.user_name),
    machine_name: formatJsonValue(log.machine_name),
    file_name: formatJsonValue(log.file_name),
    line_no: log.line_no,
    project_name: formatJsonValue(log.project_name),
    custom_fields: formatJsonValue(log.custom_fields),
  };
}
function pauseFollow(): void {
  boolFollow.value = false;
}
function resumeFollow(): void {
  if (boolFollow.value) {
    intPage.value = 1;
    arrExpanded.value = [];
    void load("newer");
  }
}
async function load(mode: "initial" | "older" | "newer"): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  strError.value = "";
  try {
    const result = await getRunLogs(
      props.runId,
      mode === "older" && intBefore !== null
        ? { before: intBefore }
        : mode === "newer"
          ? { after: intAfter }
          : {},
    );
    boolCleared.value = result.cleared;
    boolComplete.value = result.complete;
    if (result.cleared) {
      arrLog.value = [];
      intLoadedBytes.value = 0;
      boolHasMore.value = false;
      return;
    }
    const mapLog = new Map(
      (mode === "initial" ? [] : arrLog.value).map((log) => [log.log_id, log]),
    );
    for (const log of result.logs) mapLog.set(log.log_id, log);
    const arrMerged = [...mapLog.values()].sort(
      (left, right) => right.sequence - left.sequence,
    );
    let intBytes = 0;
    const arrBounded: LogEntry[] = [];
    for (const log of arrMerged) {
      const intSize = new TextEncoder().encode(JSON.stringify(log)).byteLength;
      if (arrBounded.length >= INT_MAX_ENTRIES || intBytes + intSize > INT_MAX_BYTES) {
        boolLimit.value = true;
        break;
      }
      arrBounded.push(log);
      intBytes += intSize;
    }
    arrLog.value = arrBounded;
    intLoadedBytes.value = intBytes;
    intAfter = Math.max(intAfter, result.after_cursor);
    if (mode !== "newer") {
      intBefore = result.before_cursor;
      boolHasMore.value = result.has_more;
    }
    if (mode === "initial") intPage.value = 1;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
}
function refresh(): void {
  intBefore = null;
  intAfter = 0;
  boolLimit.value = false;
  arrExpanded.value = [];
  void load("initial");
}
function loadOlder(): void {
  boolFollow.value = false;
  void load("older");
}
onMounted(() => {
  void load("initial");
  timer = setInterval(() => {
    if (boolFollow.value && props.active && !document.hidden) void load("newer");
  }, 2000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>
<style scoped></style>
