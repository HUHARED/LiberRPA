<!-- FileName: RunPackageDialog.vue -->
<template>
  <v-dialog :model-value="true" persistent max-width="1000" scrollable>
    <v-card>
      <v-card-title>Run Package</v-card-title>
      <v-card-text>
        <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
          {{ strError }}
        </v-alert>
        <v-alert v-if="originalJobActive" type="info" variant="tonal" class="mb-4">
          The original Job is still active. This creates a new independent Job.
        </v-alert>
        <v-progress-linear v-if="boolLoading" indeterminate />
        <v-form
          v-if="packageInfo && settings"
          ref="form"
          :disabled="boolBusy"
          @submit.prevent="submit">
          <p class="text-h6">{{ packageInfo.project_name }} · {{ packageInfo.version }}</p>
          <p class="mb-4">Python Environment: {{ packageInfo.python_environment_name }}</p>
          <TargetSelector
            v-model:executor-ids="arrExecutorId"
            v-model:group-id="strGroupId"
            :department-id="packageInfo.department_id"
            :disabled="boolBusy" />
          <v-divider class="my-5" />
          <h2 class="text-h6 mb-3">Run Settings</h2>
          <RunOptionsEditor
            v-model="settings"
            :department-id="packageInfo.department_id"
            :disabled="boolBusy"
            @valid="boolArgsValid = $event" />
          <v-divider class="my-5" />
          <h2 class="text-h6 mb-4">Dispatch &amp; Email</h2>
          <RunDispatchEditor v-model="settings" :disabled="boolBusy" />
          <p class="text-body-2 mt-4">
            {{ strGroupId ? 1 : arrExecutorId.length }} Jobs will be created.
          </p>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolBusy" @click="emit('close')">Cancel</v-btn>
        <v-btn
          color="primary"
          :loading="boolBusy"
          :disabled="!settings || boolLoading || !boolArgsValid"
          @click="submit">
          Run
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { shallowRef, onMounted, ref } from "vue";
import type { Ref } from "vue";
import type { VForm } from "vuetify/components";
import RunOptionsEditor from "@/components/runOptions/RunOptionsEditor.vue";
import RunDispatchEditor from "@/components/runOptions/RunDispatchEditor.vue";
import TargetSelector from "@/components/runOptions/TargetSelector.vue";
import { getPackageDetails, type PackageInfo } from "@/api/packages";
import { createJobs } from "@/api/runs";
import { cloneRunSettings, type RunSettings } from "@/api/runOptions";
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
let strRequestId = crypto.randomUUID();
let strSubmittedBody = "";
async function submit(): Promise<void> {
  if (!settings.value || !boolArgsValid.value || !(await form.value?.validate())?.valid)
    return;
  const strBody = JSON.stringify([arrExecutorId.value, strGroupId.value, settings.value]);
  if (strSubmittedBody && strSubmittedBody !== strBody) strRequestId = crypto.randomUUID();
  strSubmittedBody = strBody;
  boolBusy.value = true;
  strError.value = "";
  try {
    await createJobs(
      props.packageId,
      arrExecutorId.value,
      strGroupId.value,
      settings.value,
      strRequestId,
    );
    emit("saved");
  } catch (e) {
    strError.value = getApiError(e).message;
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
