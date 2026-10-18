<!-- FileName: ScheduleFormDialog.vue -->
<template>
  <v-dialog
    v-model="scheduleStore.showFormDialog"
    width="800px"
    height="800px"
    :persistent="boolSaving">
    <v-card v-if="currentDetail" :title="dialogTitle">
      <template #text>
        <v-container fluid class="clean-space fill-height flex-column" :inert="boolSaving">
          <v-container
            v-if="scheduleStore.formMode === 'edit' && scheduleStore.dictDetailEdit"
            fluid
            class="pa-2 ma-0 pt-0">
            <v-row class="w-100">
              <v-col cols="5" class="pb-0">
                <v-text-field
                  :model-value="
                    formatTimestamp(
                      scheduleStore.dictDetailEdit.created_at_ms,
                      settingStore.timezone,
                    )
                  "
                  label="Created At"
                  class="clean-space"
                  density="compact"
                  hide-details
                  readonly
                  variant="plain"></v-text-field>
              </v-col>

              <v-col cols="7" class="pb-0">
                <v-text-field
                  :model-value="
                    formatTimestamp(
                      scheduleStore.dictDetailEdit.updated_at_ms,
                      settingStore.timezone,
                    )
                  "
                  label="Updated At"
                  class="clean-space"
                  density="compact"
                  hide-details
                  readonly
                  variant="plain"></v-text-field>
              </v-col>
            </v-row>
          </v-container>

          <ScheduleForm />
        </v-container>
      </template>

      <v-divider></v-divider>

      <v-card-actions class="bg-surface-light">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolSaving"
          @click="scheduleStore.showFormDialog = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          variant="tonal"
          prepend-icon="mdi-content-save-outline"
          :loading="boolSaving"
          :disabled="boolSaving || !boolCanSave"
          @click="saveSchedule()">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { debounce } from "lodash";

import ScheduleForm from "./ScheduleForm.vue";

import { formatTimestamp, parseDateTimeLocalToTimestamp } from "../../Common/time";
import { loggerRenderer } from "../../Logging/logger";
import { validateCronExpression } from "../../Schedule/cron";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";
import { getErrorMessage } from "../../../../shared/error";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

const boolCanSave = ref(false);
const boolSaving = ref(false);

const currentDetail = computed(() => scheduleStore.formDraft);

const dialogTitle = computed(() =>
  scheduleStore.formMode === "new" ? "New Schedule" : "Edit Schedule",
);

const debouncedUpdateSaveState = debounce(() => {
  const detail = currentDetail.value;
  if (
    detail === undefined ||
    !validateCronExpression(detail.cron, settingStore.timezone).valid
  ) {
    boolCanSave.value = false;
    return;
  }

  if (
    detail.name === "" ||
    detail.local_package_id === undefined ||
    detail.period_start === "" ||
    detail.period_end === ""
  ) {
    boolCanSave.value = false;
    return;
  }

  const intPeriodStartMs = parseDateTimeLocalToTimestamp(
    detail.period_start,
    settingStore.timezone,
  );
  const intPeriodEndMs = parseDateTimeLocalToTimestamp(
    detail.period_end,
    settingStore.timezone,
  );
  if (
    intPeriodStartMs === undefined ||
    intPeriodEndMs === undefined ||
    intPeriodEndMs <= intPeriodStartMs
  ) {
    boolCanSave.value = false;
    return;
  }

  if (scheduleStore.formMode === "edit") {
    boolCanSave.value = JSON.stringify(detail) !== scheduleStore.strDetailCacheEdit;
    return;
  }

  boolCanSave.value = true;
}, 300);

watch(
  [currentDetail, () => settingStore.timezone],
  () => {
    debouncedUpdateSaveState();
  },
  { deep: true, immediate: true },
);

onBeforeUnmount(() => {
  debouncedUpdateSaveState.cancel();
});

async function saveSchedule(): Promise<void> {
  if (boolSaving.value) return;
  debouncedUpdateSaveState.flush();
  if (!boolCanSave.value) return;

  boolSaving.value = true;
  try {
    if (scheduleStore.formMode === "new") {
      await scheduleStore.createSchedule();
    } else if (scheduleStore.formMode === "edit") {
      await scheduleStore.saveSchedule();
    }
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to save Schedule: ${getErrorMessage(e)}`);
  } finally {
    boolSaving.value = false;
  }
}
</script>

<style scoped></style>
