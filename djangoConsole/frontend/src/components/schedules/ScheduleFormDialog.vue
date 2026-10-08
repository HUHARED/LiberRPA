<!-- FileName: ScheduleFormDialog.vue -->
<template>
  <v-dialog :model-value="true" persistent scrollable max-width="1160">
    <v-card>
      <v-card-title>{{ scheduleId ? "Edit Schedule" : "New Schedule" }}</v-card-title>
      <v-card-text>
        <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
          {{ strError }}
        </v-alert>
        <v-progress-linear v-if="boolLoading" indeterminate />
        <v-form
          v-if="boolInitialized"
          ref="form"
          :disabled="boolBusy"
          @submit.prevent="save">
          <h2 class="text-h6 mb-4">Basic &amp; Target</h2>
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strName"
                label="Name"
                maxlength="128"
                :rules="[(value) => !!value.trim() || 'Enter a name.']" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="strDepartmentId"
                :items="arrDepartment"
                item-title="path"
                item-value="id"
                label="Department"
                :readonly="!!scheduleId"
                :rules="[(value) => !!value || 'Select a department.']"
                @update:model-value="changeDepartment" />
            </v-col>
          </v-row>
          <v-row>
            <v-col cols="12" md="8">
              <v-select
                v-model="strPackageId"
                :items="arrPackage"
                :item-title="
                  (item: PackageInfo) => `${item.project_name} · ${item.version}`
                "
                item-value="id"
                label="Project / Version"
                :loading="boolPackagesLoading"
                :disabled="boolBusy || boolPackagesLoading"
                :error-messages="strPackagesError"
                :rules="[(value) => !!value || 'Select a package.']"
                @update:model-value="changePackage" />
            </v-col>
            <v-col cols="12" md="4">
              <v-switch v-model="boolEnabled" label="Enabled" />
            </v-col>
          </v-row>
          <p class="mb-4">
            Python Environment: {{ selectedPackage?.python_environment_name || "—" }}
          </p>
          <TargetSelector
            :key="strDepartmentId"
            v-model:executor-ids="arrExecutorId"
            v-model:group-id="strGroupId"
            :department-id="strDepartmentId"
            :disabled="boolBusy" />
          <p class="text-body-2 text-medium-emphasis">
            Offline or paused Executors and empty groups can be saved.
          </p>
          <v-textarea v-model="strNotes" label="Notes (optional)" rows="2" class="mt-4" />
          <v-divider class="my-5" />
          <h2 class="text-h6 mb-4">Time</h2>
          <v-text-field
            v-model="strTimeZone"
            label="Schedule Time Zone (IANA)"
            :rules="[(value) => !!value || 'Enter a time zone.']" />
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strActiveFrom"
                type="datetime-local"
                step="1"
                label="Active From"
                :rules="[(value) => !!value || 'Enter the start time.']" />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strActiveUntil"
                type="datetime-local"
                step="1"
                label="Active Until"
                :rules="[(value) => !!value || 'Enter the end time.']" />
            </v-col>
          </v-row>
          <v-row>
            <v-col cols="12" md="5">
              <v-text-field
                :model-value="strCron"
                label="Cron Expression"
                hint="Five fields, or six fields with seconds first."
                persistent-hint
                @update:model-value="changeCron" />
            </v-col>
            <v-col cols="12" md="7">
              <cron-vuetify
                v-if="strVisualCron"
                :key="intVisualRevision"
                :model-value="strVisualCron"
                :disabled="boolBusy"
                @update:model-value="changeVisualCron" />
              <p v-else class="text-body-2 text-medium-emphasis">
                Edit this rule in the Cron Expression field; it cannot be shown visually.
              </p>
            </v-col>
          </v-row>
          <p class="mt-3">{{ strDescription }}</p>
          <v-alert v-if="strPreviewError" type="error" variant="tonal" class="mt-3">
            {{ strPreviewError }}
          </v-alert>
          <h3 class="text-subtitle-1 mt-4">Upcoming Triggers · {{ strTimeZone }}</h3>
          <v-progress-linear v-if="boolPreviewLoading" indeterminate />
          <p v-for="time in arrPreview" :key="time">
            {{ formatDateTime(time, strTimeZone) }}
          </p>
          <p
            v-if="!boolPreviewLoading && !arrPreview.length && !strPreviewError"
            class="text-medium-emphasis">
            No upcoming trigger within the active period.
          </p>
          <template v-if="settings">
            <v-divider class="my-5" />
            <h2 class="text-h6 mb-4">Run Settings</h2>
            <RunOptionsEditor
              v-model="settings"
              :department-id="strDepartmentId"
              :disabled="boolBusy"
              @valid="boolArgsValid = $event" />
            <v-divider class="my-5" />
            <h2 class="text-h6 mb-4">Dispatch &amp; Email</h2>
            <RunDispatchEditor v-model="settings" :disabled="boolBusy" />
          </template>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolBusy" @click="emit('close')">Cancel</v-btn>
        <v-btn
          color="primary"
          :loading="boolBusy"
          :disabled="
            boolLoading ||
            boolPackagesLoading ||
            !boolInitialized ||
            !settings ||
            !boolArgsValid
          "
          @click="save">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import {
  shallowRef,
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import type { Ref } from "vue";
import type { VForm } from "vuetify/components";
import cronstrue from "cronstrue";
import RunOptionsEditor from "@/components/runOptions/RunOptionsEditor.vue";
import RunDispatchEditor from "@/components/runOptions/RunDispatchEditor.vue";
import TargetSelector from "@/components/runOptions/TargetSelector.vue";
import { getPackages, type PackageInfo } from "@/api/packages";
import {
  getSchedule,
  saveSchedule,
  previewSchedule,
  formatScheduleDateInput,
  type ScheduleInfo,
} from "@/api/schedules";
import { cloneRunSettings, type RunSettings } from "@/api/runOptions";
import { requestApi } from "@/api/client";
import { isRecord } from "@/api/responses";
import { getApiError } from "@/api/errors";
import { useSessionStore } from "@/stores/sessionStore";
import { formatDateTime } from "@/app/formatters";
const props = defineProps<{ scheduleId?: string }>();
const emit = defineEmits<{ close: []; saved: [schedule: ScheduleInfo] }>();
const sessionStore = useSessionStore();
const form = ref<InstanceType<typeof VForm> | null>(null);
const arrDepartment = computed(
  () =>
    sessionStore.access?.departments.filter(
      (department) => sessionStore.access?.is_org_admin || department.role === "developer",
    ) ?? [],
);
const strName = ref("");
const strDepartmentId = ref(
  arrDepartment.value.length === 1 ? arrDepartment.value[0]!.id : "",
);
const strPackageId = ref("");
const arrExecutorId = ref<string[]>([]);
const strGroupId = ref<string | null>(null);
const boolEnabled = ref(true);
const strNotes = ref("");
const strTimeZone = ref("UTC");
const strActiveFrom = ref(
  formatScheduleDateInput(new Date().toISOString(), strTimeZone.value).slice(0, 10) +
    "T00:00:00",
);
const strActiveUntil = ref("2084-04-04T00:00:00");
const strCron = ref("0 0 * * *");
const boolLoading = ref(true);
const boolInitialized = ref(false);
const boolBusy = ref(false);
const boolPackagesLoading = ref(false);
const strPackagesError = ref("");
let intPackageRevision = 0;
let boolDisposed = false;
const strError = ref("");
const boolArgsValid = ref(true);
const arrPackage = shallowRef<PackageInfo[]>([]);
const settings: Ref<RunSettings | null> = ref(null);
const selectedPackage = computed(() =>
  arrPackage.value.find((entry) => entry.id === strPackageId.value),
);
const arrPreview = ref<string[]>([]);
const strPreviewError = ref("");
const boolPreviewLoading = ref(false);
let intPreviewRevision = 0;
let previewTimer: ReturnType<typeof setTimeout> | undefined;
const intVisualRevision = ref(0);
let boolVisualSyncing = false;
const strVisualCron = computed(() => {
  const arrField = strCron.value.trim().split(/\s+/);
  if (arrField.length === 6 && arrField[0] === "0") arrField.shift();
  if (arrField.length !== 5) return "";
  const arrBound = [
    [0, 59],
    [0, 23],
    [1, 31],
    [1, 12],
    [0, 6],
  ] as const;
  // Only pass bounded, supported fields to the visual parser, not partial text input.
  for (const [intIndex, strField] of arrField.entries()) {
    const [intMin, intMax] = arrBound[intIndex]!;
    for (const strPart of strField.split(",")) {
      const match = /^(\*|\d+(?:-\d+)?)(?:\/([1-9]\d*))?$/.exec(strPart);
      if (!match) return "";
      const strRange = match[1]!;
      const strStep = match[2];
      if (
        strStep !== undefined &&
        (Number(strStep) > intMax - intMin + 1 ||
          (strRange !== "*" && !strRange.includes("-")))
      )
        return "";
      if (strRange === "*") {
        if (strField !== strPart) return "";
        continue;
      }
      const arrLimit = strRange.split("-").map(Number);
      if (
        arrLimit.some((value) => value < intMin || value > intMax) ||
        arrLimit[0]! > arrLimit[arrLimit.length - 1]! ||
        arrLimit.join("-") !== strRange
      )
        return "";
    }
  }
  // Visual normalization can change the OR semantics when both day fields are restricted.
  if (arrField[2] !== "*" && arrField[4] !== "*") return "";
  return arrField.join(" ");
});
const strDescription = computed(() => {
  try {
    return cronstrue.toString(strCron.value, {
      use24HourTimeFormat: true,
      throwExceptionOnParseError: true,
    });
  } catch {
    return "Enter a valid Cron expression.";
  }
});
async function changeCron(value: string): Promise<void> {
  strCron.value = value;
  boolVisualSyncing = true;
  const intRevision = ++intVisualRevision.value;
  // Recreate the visual editor so its selected period follows the new text.
  await nextTick();
  if (intRevision === intVisualRevision.value) boolVisualSyncing = false;
}
function changeVisualCron(value: string): void {
  // Ignore normalization emitted while the editor is loading the text draft.
  if (boolVisualSyncing || boolBusy.value || !strVisualCron.value) return;
  const boolHasSeconds = strCron.value.trim().split(/\s+/).length === 6;
  strCron.value = boolHasSeconds ? `0 ${value}` : value;
}
async function loadPackages(): Promise<void> {
  const intRevision = ++intPackageRevision;
  const strRequestedDepartmentId = strDepartmentId.value;
  arrPackage.value = [];
  strPackagesError.value = "";
  boolPackagesLoading.value = !!strRequestedDepartmentId;
  if (!strRequestedDepartmentId) return;
  try {
    const arrResult: PackageInfo[] = [];
    let intPage = 1;
    let intTotal = 1;
    do {
      const result = await getPackages([strRequestedDepartmentId], "", intPage++);
      if (intRevision !== intPackageRevision) return;
      arrResult.push(...result.packages);
      intTotal = result.total_pages;
    } while (intPage <= intTotal);
    arrPackage.value = arrResult;
  } catch (e) {
    if (intRevision === intPackageRevision) strPackagesError.value = getApiError(e).message;
  } finally {
    if (intRevision === intPackageRevision) boolPackagesLoading.value = false;
  }
}
function changeDepartment(): void {
  arrExecutorId.value = [];
  strGroupId.value = null;
  strPackageId.value = "";
  settings.value = null;
  void loadPackages();
}
function changePackage(): void {
  settings.value = selectedPackage.value
    ? cloneRunSettings(selectedPackage.value.settings)
    : null;
}
async function refreshPreview(intRevision: number): Promise<void> {
  try {
    const result = await previewSchedule({
      cron: strCron.value,
      time_zone: strTimeZone.value,
      active_from: strActiveFrom.value,
      active_until: strActiveUntil.value,
    });
    if (intRevision === intPreviewRevision) arrPreview.value = result.upcoming_triggers;
  } catch (e) {
    if (intRevision === intPreviewRevision) {
      strPreviewError.value = getApiError(e).message;
      arrPreview.value = [];
    }
  } finally {
    if (intRevision === intPreviewRevision) boolPreviewLoading.value = false;
  }
}
async function save(): Promise<void> {
  if (
    boolBusy.value ||
    boolLoading.value ||
    boolPackagesLoading.value ||
    !boolInitialized.value ||
    !settings.value ||
    !boolArgsValid.value
  )
    return;
  boolBusy.value = true;
  strError.value = "";
  try {
    if (!(await form.value?.validate())?.valid || boolDisposed) return;
    const result = await saveSchedule(props.scheduleId ?? null, {
      name: strName.value,
      department_id: strDepartmentId.value,
      package_id: strPackageId.value,
      executor_ids: arrExecutorId.value,
      group_id: strGroupId.value,
      enabled: boolEnabled.value,
      notes: strNotes.value,
      cron: strCron.value,
      time_zone: strTimeZone.value,
      active_from: strActiveFrom.value,
      active_until: strActiveUntil.value,
      settings: settings.value,
    });
    if (!boolDisposed) emit("saved", result);
  } catch (e) {
    if (!boolDisposed) strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
watch(
  [boolInitialized, strCron, strTimeZone, strActiveFrom, strActiveUntil],
  () => {
    const intRevision = ++intPreviewRevision;
    clearTimeout(previewTimer);
    arrPreview.value = [];
    strPreviewError.value = "";
    boolPreviewLoading.value = boolInitialized.value;
    if (!boolInitialized.value) return;
    previewTimer = setTimeout(() => void refreshPreview(intRevision), 400);
  },
  { flush: "sync" },
);
onMounted(async () => {
  try {
    if (!props.scheduleId) {
      const defaults = await requestApi("/schedules/defaults/");
      if (boolDisposed) return;
      if (isRecord(defaults) && typeof defaults.time_zone === "string") {
        strTimeZone.value = defaults.time_zone;
        strActiveFrom.value =
          formatScheduleDateInput(new Date().toISOString(), strTimeZone.value).slice(
            0,
            10,
          ) + "T00:00:00";
      }
    }
    if (props.scheduleId) {
      const schedule = await getSchedule(props.scheduleId);
      if (boolDisposed) return;
      strName.value = schedule.name;
      strDepartmentId.value = schedule.department_id;
      strPackageId.value = schedule.package_id;
      arrExecutorId.value = [...schedule.executor_ids];
      strGroupId.value = schedule.group_id;
      boolEnabled.value = schedule.enabled;
      strNotes.value = schedule.notes;
      strTimeZone.value = schedule.time_zone;
      strActiveFrom.value = formatScheduleDateInput(
        schedule.active_from,
        schedule.time_zone,
      );
      strActiveUntil.value = formatScheduleDateInput(
        schedule.active_until,
        schedule.time_zone,
      );
      strCron.value = schedule.cron;
      settings.value = cloneRunSettings(schedule.settings);
    }
    await loadPackages();
    if (boolDisposed) return;
    boolInitialized.value = true;
    void changeCron(strCron.value);
  } catch (e) {
    if (!boolDisposed) strError.value = getApiError(e).message;
  } finally {
    if (!boolDisposed) boolLoading.value = false;
  }
});
onBeforeUnmount(() => {
  boolDisposed = true;
  clearTimeout(previewTimer);
  intPackageRevision++;
  intPreviewRevision++;
  intVisualRevision.value++;
});
</script>
<style scoped></style>
