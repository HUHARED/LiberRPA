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
        <v-form ref="form" :disabled="boolBusy || boolLoading">
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
                v-model="strCron"
                label="Cron Expression"
                hint="Five fields, or six fields with seconds first."
                persistent-hint />
            </v-col>
            <v-col cols="12" md="7">
              <cron-vuetify
                :model-value="strVisualCron"
                @update:model-value="changeVisualCron" />
              <v-btn
                size="small"
                variant="tonal"
                class="mt-2"
                @click="strCron = strVisualCron">
                Apply Visual Rule
              </v-btn>
              <p v-if="!boolVisualSupported" class="text-body-2 text-medium-emphasis">
                Advanced Cron is preserved. Use the text field to edit it, or choose a new
                visual rule.
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
          :disabled="boolLoading || !settings || !boolArgsValid"
          @click="save">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolPackagesLoading = ref(false);
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
const boolVisualSupported = computed(() =>
  /^([\d*/,-]+ ){4}[\d*/,-]+$/.test(strCron.value.trim()),
);
const strVisualCron = ref("0 0 * * *");
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
function changeVisualCron(value: string): void {
  strVisualCron.value = value;
}
async function loadPackages(): Promise<void> {
  arrPackage.value = [];
  if (!strDepartmentId.value) return;
  boolPackagesLoading.value = true;
  try {
    let intPage = 1;
    let intTotal = 1;
    do {
      const result = await getPackages([strDepartmentId.value], "", intPage++);
      arrPackage.value = [...arrPackage.value, ...result.packages];
      intTotal = result.total_pages;
    } while (intPage <= intTotal);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolPackagesLoading.value = false;
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
  if (selectedPackage.value)
    settings.value = cloneRunSettings(selectedPackage.value.settings);
}
async function refreshPreview(): Promise<void> {
  const intRevision = ++intPreviewRevision;
  boolPreviewLoading.value = true;
  strPreviewError.value = "";
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
  if (!settings.value || !boolArgsValid.value || !(await form.value?.validate())?.valid)
    return;
  boolBusy.value = true;
  strError.value = "";
  try {
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
    emit("saved", result);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
watch([strCron, strTimeZone, strActiveFrom, strActiveUntil], () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => void refreshPreview(), 400);
});
onMounted(async () => {
  boolLoading.value = true;
  try {
    if (!props.scheduleId) {
      const defaults = await requestApi("/schedules/defaults/");
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
      if (boolVisualSupported.value) strVisualCron.value = schedule.cron;
      settings.value = cloneRunSettings(schedule.settings);
    }
    await loadPackages();
    await refreshPreview();
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
});
onBeforeUnmount(() => {
  clearTimeout(previewTimer);
  intPreviewRevision++;
});
</script>
<style scoped></style>
