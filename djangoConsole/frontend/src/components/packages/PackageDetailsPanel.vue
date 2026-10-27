<!-- FileName: PackageDetailsPanel.vue -->
<template>
  <v-card variant="flat" rounded="0" class="d-flex flex-column flex-grow-1" min-height="0">
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
          v-tooltip:bottom="
            `If an external download manager fails, use your browser's built-in downloader.`
          "
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

    <v-card-text ref="feedbackContainer" class="pa-0 overflow-hidden" style="min-height: 0">
      <v-tabs-window v-model="strTab" class="h-100">
        <v-tabs-window-item value="settings" eager class="h-100 overflow-y-auto pa-4">
          <v-form
            v-if="draft"
            ref="form"
            class="d-flex flex-column h-100"
            :disabled="boolBusy"
            :readonly="!details.package.can_manage"
            @submit.prevent="save">
            <v-alert
              v-if="strEditError"
              ref="errorAlert"
              role="alert"
              tabindex="-1"
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
                  :variant="details.package.can_manage ? 'underlined' : 'plain'"
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
              :variant="details.package.can_manage ? 'underlined' : 'plain'"
              :menu-icon="!details.package.can_manage ? '' : undefined"
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

              <TimeZoneHint :time-zone="strTimeZone" />

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
                    <td>
                      {{ formatDateTime(details.package.uploaded_at, strTimeZone, false) }}
                    </td>
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
                    <td>
                      <v-chip
                        v-if="preparation.from_previous_association"
                        v-tooltip:bottom="
                          'The current client has not reported a preparation result.'
                        "
                        color="warning"
                        size="small"
                        variant="tonal">
                        Not confirmed
                      </v-chip>

                      <v-chip
                        v-else
                        :color="PACKAGE_PREPARATION_COLORS[preparation.state]"
                        size="small"
                        variant="tonal">
                        {{ PACKAGE_PREPARATION_LABELS[preparation.state] }}
                      </v-chip>
                    </td>
                    <td>
                      {{
                        preparation.from_previous_association
                          ? "—"
                          : preparation.reason || "—"
                      }}
                    </td>
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
        :disabled="!boolCanSave"
        @click="save">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-dialog v-model="boolDelete" :persistent="boolBusy" scrollable max-width="600">
    <v-card>
      <v-card-title>Delete Package</v-card-title>

      <v-card-text ref="deleteFeedbackContainer">
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

        <v-alert
          v-if="strDeleteError"
          ref="deleteErrorAlert"
          role="alert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mt-4">
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
    <v-card ref="preparationFeedbackContainer">
      <v-card-title>Cancel Preparation Requests</v-card-title>

      <v-card-text>
        Cancel unfinished preparation requests for this package? Downloads already in
        progress may finish. Schedules, Jobs and files cached on Executors are unchanged.
        <v-alert
          v-if="strPreparationError"
          ref="preparationErrorAlert"
          role="alert"
          tabindex="-1"
          type="error"
          variant="tonal"
          class="mt-4">
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

  <PackageRunDialog
    v-if="boolRun"
    :package-id="details.package.id"
    @close="boolRun = false"
    @view-job-queue="viewJobQueue" />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { RouterLink, useRouter, type RouteLocationRaw } from "vue-router";
import type { VForm } from "vuetify/components";

import TimeZoneHint from "@/components/common/TimeZoneHint.vue";
import RunArgumentsEditor from "@/components/runSettings/RunArgumentsEditor.vue";
import RunDispatchEmailEditor from "@/components/runSettings/RunDispatchEmailEditor.vue";
import PackageRunDialog from "./PackageRunDialog.vue";

import {
  PACKAGE_REFERENCE_LABELS,
  getPackageDetails,
  savePackageSettings,
  cancelPackagePreparation,
  deletePackage,
  downloadPackage,
} from "@/api/packages";
import { cloneRunSettings, type RunSettings } from "@/api/runSettings";
import { getApiError, getFieldErrors } from "@/api/errors";
import {
  type PackageDetailsResponse,
  type PackageReferenceResponse,
  PackageReferenceKind,
  PackagePreparationState,
  DepartmentRole,
} from "@/api/generated/browserApi";

import { PACKAGE_PREPARATION_LABELS, PACKAGE_PREPARATION_COLORS } from "@/app/runLabels";
import { formatDateTime, formatFileSize } from "@/app/formatters";
import { validateEnvironmentName } from "@/app/validators";
import { revealFormFeedback } from "@/app/formFeedback";

import { useSessionStore } from "@/stores/sessionStore";

const props = defineProps<{ details: PackageDetailsResponse }>();
const emit = defineEmits<{ updated: [details: PackageDetailsResponse]; deleted: [] }>();
const sessionStore = useSessionStore();
const router = useRouter();
const form = ref<InstanceType<typeof VForm> | null>(null);
const feedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const errorAlert = ref<{ $el: HTMLElement } | null>(null);
const deleteFeedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const deleteErrorAlert = ref<{ $el: HTMLElement } | null>(null);
const preparationFeedbackContainer = ref<{ $el: HTMLElement } | null>(null);
const preparationErrorAlert = ref<{ $el: HTMLElement } | null>(null);
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
    JSON.stringify(draft.value) !== JSON.stringify(props.details.package.settings),
);

const boolCanRun = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some(
      (department) =>
        department.id === props.details.package.department_id &&
        (department.role === DepartmentRole.Operator ||
          department.role === DepartmentRole.Developer),
    ),
);

const boolHasPreparationRequests = computed(() =>
  props.details.references.some(
    (reference) => reference.kind === PackageReferenceKind.Preparation,
  ),
);

const boolBusy = ref(false);
const boolCanSave = computed(
  () =>
    !boolBusy.value &&
    !!draft.value &&
    props.details.package.can_manage &&
    boolChanged.value &&
    boolArgsValid.value &&
    !!strEnvironment.value.trim(),
);
const boolDownload = ref(false);
const boolDelete = ref(false);
const boolCancelPreparation = ref(false);
const boolRun = ref(false);
const strError = ref("");
const strDeleteError = ref("");
const strPreparationError = ref("");
const strSuccess = ref("");
let boolActive = true;

function getReferenceLocation(
  reference: PackageReferenceResponse,
): RouteLocationRaw | undefined {
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
    await downloadPackage(props.details.package.id);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolDownload.value = false;
  }
}

async function save(): Promise<void> {
  if (!boolCanSave.value || !draft.value) return;

  boolBusy.value = true;
  strEditError.value = "";
  strSuccess.value = "";
  dictFieldError.value = {};
  let boolShowFeedback = false;
  try {
    await nextTick();
    const validation = await form.value?.validate();
    if (!boolActive) return;
    if (!validation?.valid) {
      strTab.value = "settings";
      boolShowFeedback = true;
      return;
    }

    const packageDetails = await savePackageSettings(
      props.details.package.id,
      strEnvironment.value,
      draft.value,
      arrApiInputKey.value,
    );
    if (!boolActive) return;

    emit("updated", packageDetails);
    strError.value = "";
    strSuccess.value = "Settings saved.";
  } catch (e) {
    const error = getApiError(e);
    strTab.value = "settings";
    strEditError.value = error.message;
    dictFieldError.value = error.fields;
    boolShowFeedback = true;
  } finally {
    boolBusy.value = false;
    if (boolActive && boolShowFeedback) {
      await nextTick();
      revealFormFeedback(feedbackContainer.value?.$el, errorAlert.value?.$el);
    }
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
  strError.value = "";
  strSuccess.value = "";
  try {
    const intCanceledCount = await cancelPackagePreparation(props.details.package.id);
    if (!boolActive) return;

    boolCancelPreparation.value = false;
    strSuccess.value = `${intCanceledCount} preparation request(s) canceled.`;
    emit("updated", {
      ...props.details,
      preparation: props.details.preparation.filter(
        (preparation) =>
          preparation.state !== PackagePreparationState.Pending &&
          preparation.state !== PackagePreparationState.Preparing,
      ),
      references: props.details.references.filter(
        (reference) => reference.kind !== PackageReferenceKind.Preparation,
      ),
    });

    try {
      const refreshed = await getPackageDetails(props.details.package.id);
      if (boolActive) emit("updated", refreshed);
    } catch (e) {
      if (boolActive)
        strError.value = `Package details could not be refreshed. ${getApiError(e).message}`;
    }
  } catch (e) {
    if (boolActive) strPreparationError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
    if (boolActive && boolCancelPreparation.value && strPreparationError.value) {
      await nextTick();
      revealFormFeedback(
        preparationFeedbackContainer.value?.$el,
        preparationErrorAlert.value?.$el,
      );
    }
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
    if (boolActive && boolDelete.value && strDeleteError.value) {
      await nextTick();
      revealFormFeedback(deleteFeedbackContainer.value?.$el, deleteErrorAlert.value?.$el);
    }
  }
}

function viewJobQueue(): void {
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
