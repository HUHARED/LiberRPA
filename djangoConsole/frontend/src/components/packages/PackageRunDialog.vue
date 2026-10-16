<!-- FileName: PackageRunDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    :persistent="boolBusy"
    max-width="1000"
    scrollable
    @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title>Run Package</v-card-title>

      <v-card-text>
        <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
          {{ strError }}
        </v-alert>

        <v-alert
          v-if="originalJobActive && intCreatedJobCount === null"
          type="info"
          variant="tonal"
          class="mb-4">
          The original Job is still active. This creates a new independent Job.
        </v-alert>

        <v-alert v-if="intCreatedJobCount !== null" type="success" variant="tonal">
          <span class="font-weight-bold">{{ intCreatedJobCount }}</span>
          {{ intCreatedJobCount === 1 ? "Job" : "Jobs" }} created.
        </v-alert>

        <v-progress-linear v-if="boolLoading" indeterminate />

        <v-form
          v-if="packageInfo && settings && intCreatedJobCount === null"
          ref="form"
          :disabled="boolBusy"
          @submit.prevent="submit">
          <p class="text-h6">
            {{ packageInfo.project_name }} · {{ packageInfo.project_version }}
          </p>

          <p class="text-anywhere">
            Department:
            <span class="text-highlight font-weight-bold">
              {{ packageInfo.department_path }}
            </span>
          </p>

          <TargetSelector
            v-model:executor-ids="arrExecutorId"
            v-model:group-id="strGroupId"
            :department-id="packageInfo.department_id"
            :disabled="boolBusy"
            :field-errors="dictFieldError" />

          <v-divider class="my-5" />
          <h2 class="text-h6 mb-3">Run Settings</h2>

          <RunArgumentsEditor
            v-model="settings"
            :department-id="packageInfo.department_id"
            :disabled="boolBusy"
            :field-errors="dictFieldError"
            @valid="boolArgsValid = $event">
            <template #environment>
              <v-text-field
                :model-value="packageInfo.python_environment_name"
                label="Python Environment"
                variant="underlined"
                density="compact"
                readonly>
                <v-tooltip activator="parent" location="top">
                  Python environment from Package Settings. Change it there for future runs.
                </v-tooltip>
              </v-text-field>
            </template>
          </RunArgumentsEditor>

          <v-divider class="my-5" />
          <h2 class="text-h6 mb-4">Dispatch &amp; Email</h2>

          <RunDispatchEmailEditor
            v-model="settings"
            :disabled="boolBusy"
            :field-errors="dictFieldError" />

          <p class="text-body-2 mt-4">
            <span class="font-weight-bold">
              {{ strGroupId ? 1 : arrExecutorId.length }}
            </span>
            Jobs will be created.
          </p>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="emit('close')">
          {{ intCreatedJobCount === null ? "Cancel" : "Close" }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="intCreatedJobCount !== null"
          variant="tonal"
          prepend-icon="mdi-queue-first-in-last-out"
          color="primary"
          @click="emit('saved')">
          View Job Queue
        </v-btn>

        <v-btn
          v-else
          variant="tonal"
          prepend-icon="mdi-play-outline"
          color="primary"
          :loading="boolBusy"
          :disabled="!settings || boolLoading || boolBusy || !boolArgsValid"
          @click="submit">
          Run
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { shallowRef, nextTick, onMounted, ref } from "vue";
import type { Ref } from "vue";
import type { VForm } from "vuetify/components";

import RunArgumentsEditor from "@/components/runSettings/RunArgumentsEditor.vue";
import RunDispatchEmailEditor from "@/components/runSettings/RunDispatchEmailEditor.vue";
import TargetSelector from "@/components/runSettings/TargetSelector.vue";

import { getPackageDetails, type PackageInfo } from "@/api/packages";
import { createJobs } from "@/api/runs";
import { cloneRunSettings, type RunSettings } from "@/api/runSettings";
import { getApiError } from "@/api/errors";

const props = defineProps<{
  packageId: string;
  executorIds?: string[];
  groupId?: string | null;
  originalJobActive?: boolean;
}>();

const emit = defineEmits<{ close: []; saved: [] }>();
const form = ref<InstanceType<typeof VForm> | null>(null);
const packageInfo = shallowRef<PackageInfo | null>(null);
const settings: Ref<RunSettings | null> = ref(null);
const arrExecutorId = ref([...(props.executorIds ?? [])]);
const strGroupId = ref(props.groupId ?? null);
const boolLoading = ref(true);
const boolBusy = ref(false);
const boolArgsValid = ref(true);
const strError = ref("");
const dictFieldError = ref<Record<string, string[]>>({});
const intCreatedJobCount = ref<number | null>(null);
let strClientRequestId = crypto.randomUUID();
let strSubmittedBody = "";

async function submit(): Promise<void> {
  if (
    boolBusy.value ||
    boolLoading.value ||
    !settings.value ||
    !boolArgsValid.value ||
    intCreatedJobCount.value !== null
  )
    return;
  boolBusy.value = true;
  strError.value = "";
  dictFieldError.value = {};
  try {
    await nextTick();
    if (!(await form.value?.validate())?.valid) return;
    const runSettings = cloneRunSettings(settings.value);
    const arrTargetId = [...arrExecutorId.value];
    const strTargetGroupId = strGroupId.value;
    const strBody = JSON.stringify([arrTargetId, strTargetGroupId, runSettings]);
    if (strSubmittedBody && strSubmittedBody !== strBody)
      strClientRequestId = crypto.randomUUID();
    strSubmittedBody = strBody;
    const result = await createJobs(
      props.packageId,
      arrTargetId,
      strTargetGroupId,
      runSettings,
      strClientRequestId,
    );
    intCreatedJobCount.value = result.jobs.length;
  } catch (e) {
    const error = getApiError(e);
    strError.value = error.message;
    dictFieldError.value = error.fields;
  } finally {
    boolBusy.value = false;
  }
}

onMounted(async () => {
  try {
    packageInfo.value = (await getPackageDetails(props.packageId)).package;
    settings.value = cloneRunSettings(packageInfo.value.settings);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
});
</script>

<style scoped></style>
