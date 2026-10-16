<!-- FileName: ScheduleFormDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolBusy"
    scrollable
    max-width="1160"
    @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title>
        {{ scheduleId ? (boolReadonly ? "Schedule" : "Edit Schedule") : "New Schedule" }}
      </v-card-title>

      <v-card-text>
        <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
          {{ strError }}
        </v-alert>

        <v-progress-linear v-if="boolLoading" indeterminate />

        <v-form
          v-if="boolInitialized"
          ref="form"
          :disabled="boolBusy"
          :readonly="boolReadonly"
          @submit.prevent="save">
          <h2 class="text-h6 mb-4">Basic &amp; Target</h2>

          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strName"
                :error-messages="getFieldErrors(dictFieldError, 'name')"
                label="Name"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                density="compact"
                hide-details="auto"
                maxlength="128"
                :rules="[(value) => !!value.trim() || 'Enter a name.']" />
            </v-col>

            <v-col cols="6" md="3">
              <v-select
                :model-value="settings?.run_conflict_policy"
                :items="ARR_CONFLICT_POLICY_OPTION"
                :error-messages="
                  getFieldErrors(dictFieldError, 'settings.run_conflict_policy')
                "
                label="Conflict Policy"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :disabled="!settings || boolBusy"
                @update:model-value="settings && (settings.run_conflict_policy = $event)" />
            </v-col>

            <v-col cols="6" md="3">
              <v-select
                :model-value="settings?.priority"
                :items="ARR_PRIORITY_OPTION"
                :error-messages="getFieldErrors(dictFieldError, 'settings.priority')"
                label="Priority"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :disabled="!settings || boolBusy"
                @update:model-value="settings && (settings.priority = $event)" />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-textarea
                v-model="strNotes"
                :error-messages="getFieldErrors(dictFieldError, 'notes')"
                label="Notes (optional)"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                density="compact"
                hide-details="auto"
                rows="1"
                auto-grow />
            </v-col>
          </v-row>

          <v-row align="center">
            <v-col cols="12" md="3">
              <v-select
                v-model="strDepartmentId"
                :error-messages="getFieldErrors(dictFieldError, 'department_id')"
                :items="arrDepartment"
                item-title="path"
                item-value="id"
                label="Department"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :rules="[(value) => !!value || 'Select a department.']"
                @update:model-value="changeDepartment" />
            </v-col>

            <v-col cols="7" md="4">
              <v-select
                v-model="strProjectNameKey"
                :items="arrProjectOption"
                label="Project Name"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :loading="boolPackagesLoading"
                :disabled="boolBusy || boolPackagesLoading || !strDepartmentId"
                :error-messages="strPackagesError"
                :rules="[(value) => !!value || 'Select a project.']"
                @update:model-value="changeProject" />
            </v-col>

            <v-col cols="5" md="3">
              <v-select
                v-model="strPackageId"
                :items="arrProjectPackage"
                item-title="project_version"
                item-value="id"
                label="Project Version"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :loading="boolSettingsLoading"
                :disabled="boolBusy || boolPackagesLoading || !strProjectNameKey"
                :error-messages="getFieldErrors(dictFieldError, 'package_id')"
                :rules="[(value) => !!value || 'Select a project version.']"
                @update:model-value="changePackage" />
            </v-col>

            <v-col cols="12" md="2">
              <v-switch
                v-model="boolEnabled"
                :error-messages="getFieldErrors(dictFieldError, 'enabled')"
                label="Enabled"
                true-icon="mdi-flash"
                density="compact"
                hide-details="auto" />
            </v-col>
          </v-row>

          <TargetSelector
            :key="strDepartmentId"
            v-model:executor-ids="arrExecutorId"
            v-model:group-id="strGroupId"
            :field-errors="dictFieldError"
            :department-id="strDepartmentId"
            :disabled="boolBusy"
            :readonly="boolReadonly"
            class="mt-2" />

          <v-divider class="my-5" />
          <h2 class="text-h6 mb-4">Time</h2>

          <v-row>
            <v-col cols="12" md="4">
              <v-autocomplete
                v-model="strTimeZone"
                :items="arrTimeZone"
                :error-messages="getFieldErrors(dictFieldError, 'time_zone')"
                label="Schedule Time Zone"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                :menu-icon="boolReadonly ? '' : undefined"
                density="compact"
                hide-details="auto"
                :rules="[(value) => !!value || 'Select a time zone.']" />
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="strActiveFrom"
                :error-messages="getFieldErrors(dictFieldError, 'active_from')"
                type="datetime-local"
                step="1"
                label="Active From"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                density="compact"
                hide-details="auto"
                :rules="[(value) => !!value || 'Enter the start time.']" />
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="strActiveUntil"
                :error-messages="getFieldErrors(dictFieldError, 'active_until')"
                type="datetime-local"
                step="1"
                label="Active Until"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                density="compact"
                hide-details="auto"
                :rules="[(value) => !!value || 'Enter the end time.']" />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="5">
              <v-text-field
                :model-value="strCron"
                :error-messages="getFieldErrors(dictFieldError, 'cron')"
                label="Cron Expression"
                :variant="boolReadonly ? 'plain' : 'underlined'"
                density="compact"
                hint="Five fields, or six fields with seconds first."
                persistent-hint
                @update:model-value="changeCron">
                <v-tooltip activator="parent" location="top">
                  {{ strDescription }}
                </v-tooltip>
              </v-text-field>
            </v-col>

            <v-col cols="12" md="7">
              <cron-vuetify
                v-if="strVisualCron"
                :key="intVisualRevision"
                :model-value="strVisualCron"
                :disabled="boolBusy || boolReadonly"
                @update:model-value="changeVisualCron" />

              <p v-else class="text-body-2 text-medium-emphasis">
                Edit this rule in the Cron Expression field; it cannot be shown visually.
              </p>
            </v-col>
          </v-row>

          <v-alert v-if="strPreviewError" type="error" variant="tonal" class="mt-3">
            {{ strPreviewError }}
          </v-alert>

          <v-progress-linear v-if="boolPreviewLoading" indeterminate class="mt-3" />

          <v-alert
            v-else-if="!strPreviewError"
            variant="plain"
            density="compact"
            class="mt-3 px-0 text-body-2">
            Next:
            {{
              arrPreview
                .map((time) =>
                  formatDateTimeInput(time, strTimeZone, true).replace("T", " "),
                )
                .join(" · ") || "No upcoming trigger within the active period."
            }}
          </v-alert>

          <template v-if="settings">
            <v-divider class="my-5" />
            <h2 class="text-h6 mb-4">Run Settings</h2>

            <RunArgumentsEditor
              v-model="settings"
              :field-errors="dictFieldError"
              :department-id="strDepartmentId"
              :disabled="boolBusy"
              :readonly="boolReadonly"
              @valid="boolArgsValid = $event">
              <template #environment>
                <v-text-field
                  :model-value="selectedPackage?.python_environment_name ?? '—'"
                  label="Python Environment"
                  variant="plain"
                  density="compact"
                  readonly>
                  <v-tooltip activator="parent" location="top">
                    Python environment from Package Settings. Change it there for future
                    runs.
                  </v-tooltip>
                </v-text-field>
              </template>
            </RunArgumentsEditor>

            <v-divider class="my-5" />
            <h2 class="text-h6 mb-4">Run Email</h2>

            <RunEmailEditor
              v-model="settings.run_email"
              :argument-keys="settings.custom_prj_args.map((argument) => argument[0])"
              :disabled="boolBusy"
              :readonly="boolReadonly"
              :field-errors="dictFieldError" />
          </template>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="emit('close')">
          {{ boolReadonly ? "Close" : "Cancel" }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="boolReadonly && boolCanManage && boolInitialized"
          variant="tonal"
          prepend-icon="mdi-pencil-outline"
          @click="emit('edit')">
          Edit
        </v-btn>

        <v-btn
          v-if="!boolReadonly"
          variant="tonal"
          prepend-icon="mdi-content-save-outline"
          color="primary"
          :loading="boolBusy"
          :disabled="
            boolLoading ||
            boolPackagesLoading ||
            boolSettingsLoading ||
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

import RunArgumentsEditor from "@/components/runSettings/RunArgumentsEditor.vue";
import RunEmailEditor from "@/components/runSettings/RunEmailEditor.vue";
import TargetSelector from "@/components/runSettings/TargetSelector.vue";

import {
  type PackageOptionEntry,
  getPackageOptions,
  getPackageDetails,
} from "@/api/packages";
import {
  type ScheduleInfo,
  getSchedule,
  getScheduleDefaults,
  saveSchedule,
  previewSchedule,
} from "@/api/schedules";
import { type RunSettings, cloneRunSettings } from "@/api/runSettings";
import { getApiError, getFieldErrors } from "@/api/errors";

import { useSessionStore } from "@/stores/sessionStore";

import { ARR_CONFLICT_POLICY_OPTION, ARR_PRIORITY_OPTION } from "@/app/runLabels";
import { formatDateTimeInput } from "@/app/formatters";

const props = defineProps<{ scheduleId?: string; readonly?: boolean }>();
const emit = defineEmits<{ close: []; edit: []; saved: [schedule: ScheduleInfo] }>();
const sessionStore = useSessionStore();
const form = ref<InstanceType<typeof VForm> | null>(null);

const boolCanManage = ref(!props.scheduleId);
const boolReadonly = computed(() => props.readonly || !boolCanManage.value);

const arrDepartment = computed(
  () =>
    sessionStore.access?.departments.filter(
      (department) =>
        !boolCanManage.value ||
        sessionStore.access?.is_org_admin ||
        department.role === "developer",
    ) ?? [],
);

const strName = ref("");

const strDepartmentId = ref(
  arrDepartment.value.length === 1 ? arrDepartment.value[0]!.id : "",
);

const strProjectNameKey = ref("");
const strPackageId = ref("");
const arrExecutorId = ref<string[]>([]);
const strGroupId = ref<string | null>(null);
const boolEnabled = ref(true);
const strNotes = ref("");
const strTimeZone = ref("UTC");
const arrSupportedTimeZone = Intl.supportedValuesOf("timeZone");

const arrTimeZone = computed(() =>
  [...new Set(["UTC", strTimeZone.value, ...arrSupportedTimeZone])].sort(),
);

const strActiveFrom = ref(
  formatDateTimeInput(new Date().toISOString(), strTimeZone.value, true).slice(0, 10) +
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
let intSettingsRevision = 0;
const boolSettingsLoading = ref(false);
let boolDisposed = false;
const strError = ref("");
const dictFieldError = ref<Record<string, string[]>>({});
const boolArgsValid = ref(true);
const arrPackage = shallowRef<PackageOptionEntry[]>([]);
const settings: Ref<RunSettings | null> = ref(null);

const selectedPackage = computed(() =>
  arrPackage.value.find((entry) => entry.id === strPackageId.value),
);

const arrProjectOption = computed(() => {
  const mapProject = new Map<string, { title: string; value: string }>();
  for (const packageEntry of arrPackage.value) {
    if (!mapProject.has(packageEntry.project_name_key))
      mapProject.set(packageEntry.project_name_key, {
        title: packageEntry.project_name,
        value: packageEntry.project_name_key,
      });
  }
  return [...mapProject.values()];
});

const arrProjectPackage = computed(() =>
  arrPackage.value.filter(
    (packageEntry) => packageEntry.project_name_key === strProjectNameKey.value,
  ),
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

async function loadPackages(): Promise<void> {
  const intRevision = ++intPackageRevision;
  const strRequestedDepartmentId = strDepartmentId.value;
  arrPackage.value = [];
  strPackagesError.value = "";
  boolPackagesLoading.value = !!strRequestedDepartmentId;
  if (!strRequestedDepartmentId) return;
  try {
    const arrResult = await getPackageOptions(strRequestedDepartmentId);
    if (intRevision === intPackageRevision) arrPackage.value = arrResult;
  } catch (e) {
    if (intRevision === intPackageRevision) strPackagesError.value = getApiError(e).message;
  } finally {
    if (intRevision === intPackageRevision) boolPackagesLoading.value = false;
  }
}

function changeDepartment(): void {
  intSettingsRevision += 1;
  boolSettingsLoading.value = false;
  arrExecutorId.value = [];
  strGroupId.value = null;
  strProjectNameKey.value = "";
  strPackageId.value = "";
  settings.value = null;
  void loadPackages();
}

async function changePackage(): Promise<void> {
  const intRevision = ++intSettingsRevision;
  const strSelectedPackageId = strPackageId.value;
  settings.value = null;
  strPackagesError.value = "";
  boolSettingsLoading.value = !!strSelectedPackageId;
  if (!strSelectedPackageId) return;
  try {
    const result = await getPackageDetails(strSelectedPackageId);
    if (intRevision === intSettingsRevision)
      settings.value = cloneRunSettings(result.package.settings);
  } catch (e) {
    if (intRevision === intSettingsRevision)
      strPackagesError.value = getApiError(e).message;
  } finally {
    if (intRevision === intSettingsRevision) boolSettingsLoading.value = false;
  }
}

function changeProject(): void {
  strPackageId.value = arrProjectPackage.value[0]?.id ?? "";
  void changePackage();
}

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
  if (boolVisualSyncing || boolBusy.value || boolReadonly.value || !strVisualCron.value)
    return;
  const boolHasSeconds = strCron.value.trim().split(/\s+/).length === 6;
  strCron.value = boolHasSeconds ? `0 ${value}` : value;
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
    boolReadonly.value ||
    boolBusy.value ||
    boolLoading.value ||
    boolPackagesLoading.value ||
    boolSettingsLoading.value ||
    !boolInitialized.value ||
    !settings.value ||
    !boolArgsValid.value
  )
    return;
  boolBusy.value = true;
  strError.value = "";
  dictFieldError.value = {};
  try {
    await nextTick();
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
    if (!boolDisposed) {
      const error = getApiError(e);
      strError.value = error.message;
      dictFieldError.value = error.fields;
    }
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
      const defaults = await getScheduleDefaults();
      if (boolDisposed) return;
      strTimeZone.value = defaults.time_zone;
      strActiveFrom.value =
        formatDateTimeInput(new Date().toISOString(), strTimeZone.value, true).slice(
          0,
          10,
        ) + "T00:00:00";
    }
    if (props.scheduleId) {
      const schedule = await getSchedule(props.scheduleId);
      if (boolDisposed) return;
      boolCanManage.value = schedule.can_manage;
      strName.value = schedule.name;
      strDepartmentId.value = schedule.department_id;
      strPackageId.value = schedule.package_id;
      arrExecutorId.value = [...schedule.executor_ids];
      strGroupId.value = schedule.group_id;
      boolEnabled.value = schedule.enabled;
      strNotes.value = schedule.notes;
      strTimeZone.value = schedule.time_zone;
      strActiveFrom.value = formatDateTimeInput(
        schedule.active_from,
        schedule.time_zone,
        true,
      );
      strActiveUntil.value = formatDateTimeInput(
        schedule.active_until,
        schedule.time_zone,
        true,
      );
      strCron.value = schedule.cron;
      settings.value = cloneRunSettings(schedule.settings);
    }
    await loadPackages();
    if (boolDisposed) return;
    strProjectNameKey.value = selectedPackage.value?.project_name_key ?? "";
    boolInitialized.value = true;
    void changeCron(strCron.value);
  } catch (e) {
    if (!boolDisposed) {
      const error = getApiError(e);
      strError.value = error.message;
      dictFieldError.value = error.fields;
    }
  } finally {
    if (!boolDisposed) boolLoading.value = false;
  }
});

onBeforeUnmount(() => {
  boolDisposed = true;
  clearTimeout(previewTimer);
  intPackageRevision++;
  intSettingsRevision++;
  intPreviewRevision++;
  intVisualRevision.value++;
});
</script>

<style scoped></style>
