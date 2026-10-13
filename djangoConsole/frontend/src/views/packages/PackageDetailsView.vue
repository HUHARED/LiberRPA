<!-- FileName: PackageDetailsView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-2 mb-4">
    <v-btn to="/packages" variant="tonal" prepend-icon="mdi-arrow-left">
      Back to Packages
    </v-btn>
    <v-spacer />
    <v-btn :loading="boolLoading" variant="tonal" @click="load">Refresh</v-btn>
  </div>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4">
    {{ strSuccess }}
  </v-alert>
  <template v-if="details">
    <h1 class="text-h5 mb-2">
      {{ details.package.project_name }} · {{ details.package.project_version }}
    </h1>
    <p class="mb-4 text-medium-emphasis">{{ details.package.department_path }}</p>
    <div class="d-flex flex-wrap ga-2 mb-4">
      <v-btn v-if="boolCanRun" color="primary" variant="tonal" @click="boolRun = true">
        Run
      </v-btn>
      <v-btn v-if="details.package.can_manage" variant="tonal" @click="edit">
        Edit Settings
      </v-btn>
      <v-btn variant="tonal" :loading="boolDownload" @click="download">
        Download Package
      </v-btn>
      <v-btn
        v-if="details.package.can_manage"
        color="error"
        variant="tonal"
        @click="boolDelete = true">
        Delete
      </v-btn>
    </div>
    <v-tabs v-model="strTab" show-arrows>
      <v-tab value="settings">Settings</v-tab>
      <v-tab value="metadata">Package</v-tab>
      <v-tab value="preparation">Preparation</v-tab>
      <v-tab value="references">References</v-tab>
    </v-tabs>
    <v-tabs-window v-model="strTab" class="mt-4">
      <v-tabs-window-item value="settings">
        <v-card variant="outlined">
          <v-card-text>
            <RunSettingsDetails
              :settings="details.package.settings"
              :python-environment-name="details.package.python_environment_name" />
            <v-table class="mt-4">
              <tbody>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">
                    Conflict Policy
                  </th>
                  <td>
                    {{
                      CONFLICT_POLICY_LABELS[details.package.settings.run_conflict_policy]
                    }}
                  </td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">Priority</th>
                  <td>{{ PRIORITY_LABELS[details.package.settings.priority] }}</td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">
                    API Input Keys
                  </th>
                  <td>
                    {{ details.package.api_input_keys.join(", ") || "None" }}
                  </td>
                </tr>
              </tbody>
            </v-table>
            <h3 class="text-subtitle-1 mt-4">Asset Bindings</h3>
            <p
              v-for="(binding, index) in details.package.settings.custom_arg_assets"
              v-show="binding"
              :key="index">
              {{ details.package.settings.custom_prj_args[index]?.[0] }} →
              {{ binding?.name }} ({{ binding?.asset_type }})
            </p>
            <h3 class="text-subtitle-1 mt-4 mb-2">Run Email</h3>
            <RunEmailEditor
              :model-value="details.package.settings.run_email"
              :argument-keys="
                details.package.settings.custom_prj_args.map(
                  (argument: [string, unknown]) => argument[0],
                )
              "
              disabled />
          </v-card-text>
        </v-card>
      </v-tabs-window-item>
      <v-tabs-window-item value="metadata">
        <v-card variant="outlined">
          <v-card-text>
            <p class="text-pre-wrap mb-4">
              {{ details.package.description || "No description." }}
            </p>
            <v-table>
              <tbody>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">
                    Version Summary
                  </th>
                  <td class="text-pre-wrap">
                    {{ details.package.version_summary || "—" }}
                  </td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">
                    Requires LiberRPA
                  </th>
                  <td>{{ details.package.requires_liberrpa }}</td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">Size</th>
                  <td>{{ formatFileSize(details.package.size_bytes) }}</td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">Uploaded At</th>
                  <td>{{ formatDateTime(details.package.uploaded_at, strTimeZone) }}</td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">Uploaded By</th>
                  <td>{{ details.package.uploaded_by_name }}</td>
                </tr>
                <tr>
                  <th scope="row" class="text-caption text-medium-emphasis">SHA-256</th>
                  <td class="text-break">{{ details.package.sha256 }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-tabs-window-item>
      <v-tabs-window-item value="preparation">
        <v-card variant="outlined">
          <v-card-text>
            <v-btn
              v-if="details.package.can_manage && boolHasPreparationRequests"
              class="mb-4"
              variant="tonal"
              :disabled="boolBusy"
              @click="openCancelPreparation">
              Cancel Preparation Requests
            </v-btn>
            <v-table>
              <thead>
                <tr>
                  <th>Executor</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="preparation in details.preparation"
                  :key="preparation.executor_id">
                  <td>
                    <RouterLink
                      :to="{
                        name: 'executor-details',
                        params: { executorId: preparation.executor_id },
                      }"
                      class="text-primary text-decoration-none">
                      {{ preparation.executor_name }}
                    </RouterLink>
                  </td>
                  <td>{{ PACKAGE_PREPARATION_LABELS[preparation.state] }}</td>
                  <td>{{ preparation.reason || "—" }}</td>
                </tr>
                <tr v-if="!details.preparation.length">
                  <td colspan="3">No preparation reports.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-tabs-window-item>
      <v-tabs-window-item value="references">
        <v-card variant="outlined">
          <v-card-text>
            <p v-if="!details.references.length">No active references.</p>
            <v-list v-else>
              <v-list-item
                v-for="reference in details.references"
                :key="`${reference.kind}:${reference.id}`"
                :title="reference.name"
                :subtitle="PACKAGE_REFERENCE_LABELS[reference.kind]"
                :to="getReferenceLocation(reference)" />
            </v-list>
          </v-card-text>
        </v-card>
      </v-tabs-window-item>
    </v-tabs-window>
  </template>
  <v-dialog v-model="boolEdit" persistent scrollable max-width="1080">
    <v-card v-if="draft && details">
      <v-card-title>Edit Package Settings</v-card-title>
      <v-card-text>
        <v-form ref="form" :disabled="boolBusy">
          <v-alert v-if="strEditError" type="error" variant="tonal" class="mb-4">
            {{ strEditError }}
          </v-alert>
          <RunOptionsEditor
            v-model="draft"
            :field-errors="dictFieldError"
            :department-id="details.package.department_id"
            :disabled="boolBusy"
            @valid="boolArgsValid = $event">
            <template #environment>
              <v-text-field
                v-model="strEnvironment"
                :error-messages="getFieldErrors(dictFieldError, 'python_environment_name')"
                label="Python Environment"
                variant="underlined"
                density="compact"
                :rules="[validateEnvironmentName]" />
            </template>
          </RunOptionsEditor>
          <v-select
            v-model="arrApiInputKey"
            :error-messages="getFieldErrors(dictFieldError, 'api_input_keys')"
            :items="[
              ...new Set(
                draft.custom_prj_args.map((argument: [string, unknown]) => argument[0]),
              ),
            ]"
            label="API Input Keys"
            class="mt-3"
            multiple
            chips
            hint="Only these inputs can be supplied through an API key."
            persistent-hint />
          <h3 class="text-h6 my-4">Dispatch &amp; Email</h3>
          <RunDispatchEmailEditor
            v-model="draft"
            :disabled="boolBusy"
            :field-errors="dictFieldError" />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="boolEdit = false">Cancel</v-btn>
        <v-btn
          variant="tonal"
          color="primary"
          :loading="boolBusy"
          :disabled="!boolArgsValid"
          @click="save">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog v-model="boolDelete" persistent scrollable max-width="600">
    <v-card>
      <v-card-title>Delete Package</v-card-title>
      <v-card-text>
        <p>Delete this package? Existing Run history is retained.</p>
        <p v-if="details?.references.length" class="mt-3">
          Resolve these references before deleting:
        </p>
        <v-list v-if="details?.references.length">
          <v-list-item
            v-for="reference in details.references"
            :key="`${reference.kind}:${reference.id}`"
            :title="reference.name"
            :subtitle="PACKAGE_REFERENCE_LABELS[reference.kind]"
            :to="getReferenceLocation(reference)" />
        </v-list>
        <v-alert v-if="strDeleteError" type="error" variant="tonal" class="mt-4">
          {{ strDeleteError }}
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="boolDelete = false">
          Cancel
        </v-btn>
        <v-btn variant="tonal" color="error" :loading="boolBusy" @click="remove">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <v-dialog v-model="boolCancelPreparation" persistent max-width="600">
    <v-card>
      <v-card-title>Cancel Preparation Requests</v-card-title>
      <v-card-text>
        Cancel unfinished preparation requests for this package? Downloads already in
        progress may finish. Schedules, Jobs and files cached on Executors are unchanged.
        <v-alert v-if="strPreparationError" type="error" variant="tonal" class="mt-4">
          {{ strPreparationError }}
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="boolCancelPreparation = false">
          Back
        </v-btn>
        <v-btn variant="tonal" color="error" :loading="boolBusy" @click="cancelPreparation">
          Cancel Requests
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <RunPackageDialog
    v-if="boolRun"
    :package-id="packageId"
    @close="boolRun = false"
    @saved="handleRun" />
</template>
<script setup lang="ts">
import { nextTick, shallowRef, computed, ref, watch } from "vue";
import { RouterLink, useRouter, type RouteLocationRaw } from "vue-router";
import type { Ref } from "vue";
import type { VForm } from "vuetify/components";

import RunSettingsDetails from "@/components/runOptions/RunSettingsDetails.vue";
import RunOptionsEditor from "@/components/runOptions/RunOptionsEditor.vue";
import RunDispatchEmailEditor from "@/components/runOptions/RunDispatchEmailEditor.vue";
import RunEmailEditor from "@/components/runOptions/RunEmailEditor.vue";
import RunPackageDialog from "@/components/packages/RunPackageDialog.vue";

import {
  PackageReferenceKind,
  PACKAGE_REFERENCE_LABELS,
  type PackageReference,
  type PackageDetails,
  getPackageDetails,
  savePackageSettings,
  cancelPackagePreparation,
  deletePackage,
  downloadPackage,
} from "@/api/packages";
import { type RunSettings, cloneRunSettings } from "@/api/runOptions";
import { getApiError, getFieldErrors } from "@/api/errors";

import {
  CONFLICT_POLICY_LABELS,
  PRIORITY_LABELS,
  PACKAGE_PREPARATION_LABELS,
} from "@/app/runLabels";
import { formatDateTime, formatFileSize } from "@/app/formatters";
import { validateEnvironmentName } from "@/app/validators";
import { useSessionStore } from "@/stores/sessionStore";

const props = defineProps<{ packageId: string }>();
const sessionStore = useSessionStore();
const router = useRouter();
const form = ref<InstanceType<typeof VForm> | null>(null);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const details = shallowRef<PackageDetails | null>(null);
const draft: Ref<RunSettings | null> = ref(null);
const arrApiInputKey = ref<string[]>([]);
const strEnvironment = ref("");
const strTab = ref("settings");
const boolCanRun = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some(
      (department) =>
        department.id === details.value?.package.department_id &&
        ["operator", "developer"].includes(department.role ?? ""),
    ),
);
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolDownload = ref(false);
const boolEdit = ref(false);
const boolDelete = ref(false);
const boolCancelPreparation = ref(false);
const boolHasPreparationRequests = computed(
  () =>
    details.value?.references.some(
      (reference) => reference.kind === PackageReferenceKind.Preparation,
    ) ?? false,
);
const boolRun = ref(false);
const boolArgsValid = ref(true);
const strError = ref("");
const strEditError = ref("");
const dictFieldError = ref<Record<string, string[]>>({});
const strDeleteError = ref("");
const strPreparationError = ref("");
const strSuccess = ref("");

let intLoadRevision = 0;

function getReferenceLocation(reference: PackageReference): RouteLocationRaw | undefined {
  return reference.kind === PackageReferenceKind.Schedule
    ? { name: "schedule-details", params: { scheduleId: reference.id } }
    : reference.kind === PackageReferenceKind.Job
      ? { name: "job-details", params: { jobId: reference.id } }
      : undefined;
}

async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getPackageDetails(props.packageId);
    if (intRevision === intLoadRevision) details.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

async function download(): Promise<void> {
  if (!details.value) return;
  boolDownload.value = true;
  strError.value = "";
  try {
    await downloadPackage(details.value.package);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolDownload.value = false;
  }
}

function edit(): void {
  if (!details.value) return;
  draft.value = cloneRunSettings(details.value.package.settings);
  arrApiInputKey.value = [...details.value.package.api_input_keys];
  strEnvironment.value = details.value.package.python_environment_name;
  strEditError.value = "";
  dictFieldError.value = {};
  boolEdit.value = true;
}

async function save(): Promise<void> {
  if (boolBusy.value || !draft.value || !boolArgsValid.value) return;
  boolBusy.value = true;
  strEditError.value = "";
  dictFieldError.value = {};
  try {
    await nextTick();
    if (!(await form.value?.validate())?.valid) return;
    await savePackageSettings(
      props.packageId,
      strEnvironment.value,
      draft.value,
      arrApiInputKey.value,
    );
    boolEdit.value = false;
    strSuccess.value = "Settings saved.";
    await load();
  } catch (e) {
    const error = getApiError(e);
    strEditError.value = error.message;
    dictFieldError.value = error.fields;
  } finally {
    boolBusy.value = false;
  }
}

function openCancelPreparation(): void {
  strPreparationError.value = "";
  boolCancelPreparation.value = true;
}

async function cancelPreparation(): Promise<void> {
  if (boolBusy.value || !details.value?.package.can_manage) return;
  const strPackageId = props.packageId;
  boolBusy.value = true;
  strPreparationError.value = "";
  try {
    const intCanceledCount = await cancelPackagePreparation(strPackageId);
    if (strPackageId !== props.packageId) return;
    boolCancelPreparation.value = false;
    strSuccess.value = `${intCanceledCount} preparation request(s) canceled.`;
    await load();
  } catch (e) {
    if (strPackageId === props.packageId)
      strPreparationError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}

async function remove(): Promise<void> {
  if (boolBusy.value) return;
  boolBusy.value = true;
  strDeleteError.value = "";
  try {
    await deletePackage(props.packageId);
    await router.push({ name: "packages" });
  } catch (e) {
    strDeleteError.value = getApiError(e).message;
    await load();
  } finally {
    boolBusy.value = false;
  }
}

function handleRun(): void {
  boolRun.value = false;
  void router.push({ name: "job-queue" });
}

watch(
  () => props.packageId,
  () => {
    boolCancelPreparation.value = false;
    details.value = null;
    void load();
  },
  { immediate: true },
);
</script>
<style scoped></style>
