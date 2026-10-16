<!-- FileName: PackageDetailsPanel.vue -->
<template>
  <v-card
    variant="flat"
    rounded="0"
    class="d-flex flex-column flex-grow-1"
    style="min-height: 0">
    <v-card-text class="flex-grow-0 pb-2">
      <h2 class="text-h6 text-break mb-3">
        {{ details.package.project_name }} · {{ details.package.project_version }}
      </h2>

      <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
        {{ strError }}
      </v-alert>

      <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4">
        {{ strSuccess }}
      </v-alert>

      <div class="d-flex flex-wrap ga-2 mb-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-download"
          :loading="boolDownload"
          @click="download">
          Download Package
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="details.package.can_manage"
          color="error"
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          :disabled="boolBusy"
          @click="boolDelete = true">
          Delete
        </v-btn>

        <v-btn
          v-if="boolCanRun"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-play-outline"
          :disabled="boolChanged || boolBusy"
          @click="boolRun = true">
          Run
        </v-btn>
      </div>
    </v-card-text>

    <v-tabs v-model="strTab" :disabled="boolBusy" show-arrows class="flex-shrink-0 mx-4">
      <v-tab value="settings">Settings</v-tab>
      <v-tab value="metadata">Package</v-tab>
      <v-tab value="preparation">Preparation</v-tab>
      <v-tab value="references">References</v-tab>
    </v-tabs>

    <v-card-text class="pa-0 overflow-hidden" style="min-height: 0">
      <v-tabs-window v-model="strTab" class="h-100">
        <v-tabs-window-item value="settings" eager class="h-100 overflow-y-auto pa-4">
          <v-form
            v-if="draft"
            ref="form"
            class="d-flex flex-column h-100"
            :disabled="boolBusy"
            :readonly="!details.package.can_manage">
            <v-alert
              v-if="strEditError"
              type="error"
              variant="tonal"
              class="mb-4 flex-shrink-0">
              {{ strEditError }}
            </v-alert>

            <RunArgumentsEditor
              v-model="draft"
              class="flex-grow-1 flex-shrink-0"
              :field-errors="dictFieldError"
              :department-id="details.package.department_id"
              :disabled="boolBusy"
              :readonly="!details.package.can_manage"
              @valid="boolArgsValid = $event">
              <template #environment>
                <v-text-field
                  v-model="strEnvironment"
                  :error-messages="
                    getFieldErrors(dictFieldError, 'python_environment_name')
                  "
                  label="Python Environment"
                  variant="underlined"
                  density="compact"
                  :rules="[validateEnvironmentName]">
                  <v-tooltip activator="parent" location="top">
                    Name of the Python environment used to run this package.
                    <template v-if="!details.package.can_manage">
                      A department developer or organization administrator can change it in
                      Package Settings.
                    </template>
                  </v-tooltip>
                </v-text-field>
              </template>
            </RunArgumentsEditor>

            <v-select
              v-model="arrApiInputKey"
              :error-messages="getFieldErrors(dictFieldError, 'api_input_keys')"
              :items="[...new Set(draft.custom_prj_args.map((argument) => argument[0]))]"
              label="API Input Keys"
              variant="underlined"
              class="mt-3 flex-grow-0 flex-shrink-0"
              multiple
              chips
              hint="Only these inputs can be supplied through an API key."
              persistent-hint />

            <v-sheet class="flex-shrink-0">
              <h3 class="text-h6 my-4">Dispatch &amp; Email</h3>

              <RunDispatchEmailEditor
                v-model="draft"
                :disabled="boolBusy"
                :readonly="!details.package.can_manage"
                :field-errors="dictFieldError" />
            </v-sheet>
          </v-form>
        </v-tabs-window-item>

        <v-tabs-window-item value="metadata" class="h-100 overflow-y-auto pa-4">
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
                    <th scope="row" class="text-caption text-medium-emphasis">
                      Uploaded At
                    </th>
                    <td>{{ formatDateTime(details.package.uploaded_at, strTimeZone) }}</td>
                  </tr>

                  <tr>
                    <th scope="row" class="text-caption text-medium-emphasis">
                      Uploaded By
                    </th>
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

        <v-tabs-window-item value="preparation" class="h-100 overflow-y-auto pa-4">
          <v-card variant="outlined">
            <v-card-text>
              <div class="d-flex justify-end">
                <v-btn
                  v-if="details.package.can_manage && boolHasPreparationRequests"
                  class="mb-4"
                  variant="tonal"
                  prepend-icon="mdi-cancel"
                  :disabled="boolBusy"
                  @click="openCancelPreparation">
                  Cancel Preparation Requests
                </v-btn>
              </div>

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

        <v-tabs-window-item value="references" class="h-100 overflow-y-auto pa-4">
          <v-card variant="outlined">
            <v-card-text>
              <p v-if="!details.references.length">No active references.</p>

              <v-list v-else>
                <v-list-item
                  v-for="reference in details.references"
                  :key="`${reference.kind}:${reference.id}`"
                  :subtitle="PACKAGE_REFERENCE_LABELS[reference.kind]"
                  :to="getReferenceLocation(reference)"
                  class="text-decoration-none">
                  <template #title>
                    <span :class="{ 'text-primary': !!getReferenceLocation(reference) }">
                      {{ reference.name }}
                    </span>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card-text>

    <v-card-actions v-if="strTab === 'settings'" class="px-4 border-t-thin">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-close"
        :disabled="!details.package.can_manage || !boolChanged || boolBusy"
        @click="resetDraft">
        Cancel
      </v-btn>
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-content-save-outline"
        color="primary"
        :loading="boolBusy"
        :disabled="!details.package.can_manage || !boolChanged || !boolArgsValid"
        @click="save">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-dialog v-model="boolDelete" :persistent="boolBusy" scrollable max-width="600">
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
            :subtitle="PACKAGE_REFERENCE_LABELS[reference.kind]"
            :to="getReferenceLocation(reference)"
            class="text-decoration-none">
            <template #title>
              <span :class="{ 'text-primary': !!getReferenceLocation(reference) }">
                {{ reference.name }}
              </span>
            </template>
          </v-list-item>
        </v-list>

        <v-alert v-if="strDeleteError" type="error" variant="tonal" class="mt-4">
          {{ strDeleteError }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="boolDelete = false">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          color="error"
          :loading="boolBusy"
          @click="remove">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="boolCancelPreparation" :persistent="boolBusy" max-width="600">
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
        <v-btn
          variant="tonal"
          prepend-icon="mdi-arrow-left"
          :disabled="boolBusy"
          @click="boolCancelPreparation = false">
          Back
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-cancel"
          color="error"
          :loading="boolBusy"
          @click="cancelPreparation">
          Cancel Requests
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <RunPackageDialog
    v-if="boolRun"
    :package-id="details.package.id"
    @close="boolRun = false"
    @saved="handleRun" />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { RouterLink, useRouter, type RouteLocationRaw } from "vue-router";
import type { VForm } from "vuetify/components";

import RunArgumentsEditor from "@/components/runSettings/RunArgumentsEditor.vue";
import RunDispatchEmailEditor from "@/components/runSettings/RunDispatchEmailEditor.vue";
import RunPackageDialog from "./RunPackageDialog.vue";

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
import { cloneRunSettings, type RunSettings } from "@/api/runSettings";
import { getApiError, getFieldErrors } from "@/api/errors";

import { PACKAGE_PREPARATION_LABELS } from "@/app/runLabels";
import { formatDateTime, formatFileSize } from "@/app/formatters";
import { validateEnvironmentName } from "@/app/validators";

import { useSessionStore } from "@/stores/sessionStore";

const props = defineProps<{ details: PackageDetails }>();
const emit = defineEmits<{ updated: [details: PackageDetails]; deleted: [] }>();
const sessionStore = useSessionStore();
const router = useRouter();
const form = ref<InstanceType<typeof VForm> | null>(null);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const strTab = ref("settings");

const draft: Ref<RunSettings | null> = ref(null);
const arrApiInputKey = ref<string[]>([]);
const strEnvironment = ref("");
const boolArgsValid = ref(true);
const dictFieldError = ref<Record<string, string[]>>({});
const strEditError = ref("");

const boolChanged = computed(
  () =>
    !boolArgsValid.value ||
    strEnvironment.value !== props.details.package.python_environment_name ||
    JSON.stringify(arrApiInputKey.value) !==
      JSON.stringify(props.details.package.api_input_keys) ||
    JSON.stringify(draft.value) !==
      JSON.stringify(cloneRunSettings(props.details.package.settings)),
);

const boolCanRun = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some(
      (department) =>
        department.id === props.details.package.department_id &&
        ["operator", "developer"].includes(department.role ?? ""),
    ),
);

const boolHasPreparationRequests = computed(() =>
  props.details.references.some(
    (reference) => reference.kind === PackageReferenceKind.Preparation,
  ),
);

const boolBusy = ref(false);
const boolDownload = ref(false);
const boolDelete = ref(false);
const boolCancelPreparation = ref(false);
const boolRun = ref(false);
const strError = ref("");
const strDeleteError = ref("");
const strPreparationError = ref("");
const strSuccess = ref("");
let boolActive = true;

function getReferenceLocation(reference: PackageReference): RouteLocationRaw | undefined {
  return reference.kind === PackageReferenceKind.Schedule
    ? { name: "schedule", params: { scheduleId: reference.id } }
    : reference.kind === PackageReferenceKind.Job
      ? { name: "job-details", params: { jobId: reference.id } }
      : undefined;
}

function resetDraft(): void {
  draft.value = cloneRunSettings(props.details.package.settings);
  arrApiInputKey.value = [...props.details.package.api_input_keys];
  strEnvironment.value = props.details.package.python_environment_name;
  boolArgsValid.value = true;
  strEditError.value = "";
  dictFieldError.value = {};
  form.value?.resetValidation();
}

async function download(): Promise<void> {
  if (boolDownload.value) return;

  boolDownload.value = true;
  strError.value = "";
  try {
    await downloadPackage(props.details.package);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolDownload.value = false;
  }
}

async function save(): Promise<void> {
  if (
    boolBusy.value ||
    !draft.value ||
    !props.details.package.can_manage ||
    !boolChanged.value ||
    !boolArgsValid.value
  )
    return;

  boolBusy.value = true;
  strEditError.value = "";
  strSuccess.value = "";
  dictFieldError.value = {};
  try {
    await nextTick();
    const validation = await form.value?.validate();
    if (!boolActive) return;
    if (!validation?.valid) {
      strTab.value = "settings";
      return;
    }

    const packageInfo = await savePackageSettings(
      props.details.package.id,
      strEnvironment.value,
      draft.value,
      arrApiInputKey.value,
    );
    if (!boolActive) return;

    emit("updated", { ...props.details, package: packageInfo });
    strSuccess.value = "Settings saved.";
  } catch (e) {
    const error = getApiError(e);
    strTab.value = "settings";
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
  if (boolBusy.value || !props.details.package.can_manage) return;

  boolBusy.value = true;
  strPreparationError.value = "";
  try {
    const intCanceledCount = await cancelPackagePreparation(props.details.package.id);
    const refreshed = await getPackageDetails(props.details.package.id);
    if (!boolActive) return;

    emit("updated", { ...refreshed, package: props.details.package });
    boolCancelPreparation.value = false;
    strSuccess.value = `${intCanceledCount} preparation request(s) canceled.`;
  } catch (e) {
    strPreparationError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}

async function remove(): Promise<void> {
  if (boolBusy.value || !props.details.package.can_manage) return;

  boolBusy.value = true;
  strDeleteError.value = "";
  try {
    await deletePackage(props.details.package.id);
    if (boolActive) emit("deleted");
  } catch (e) {
    strDeleteError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}

function handleRun(): void {
  boolRun.value = false;
  void router.push({ name: "job-queue" });
}

watch(() => props.details.package, resetDraft, { immediate: true });

watch(strTab, (_strTab, strPreviousTab) => {
  if (strPreviousTab === "settings") resetDraft();
});

onBeforeUnmount(() => {
  boolActive = false;
});
</script>

<style scoped></style>
