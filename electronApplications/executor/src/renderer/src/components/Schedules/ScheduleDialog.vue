<!-- FileName: ScheduleDialog.vue -->
<template>
  <v-card v-if="currentDetail" :title="dialogTitle">
    <template #text>
      <v-container fluid class="clean-space fill-height flex-column">
        <v-container
          v-if="scheduleStore.formMode === 'edit' && scheduleStore.dictDetailEdit"
          fluid
          class="pa-2 ma-0 pb-0">
          <v-row class="w-100">
            <v-col cols="6" class="pb-0">
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
                variant="plain">
              </v-text-field>
            </v-col>

            <v-col cols="6" class="pb-0">
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
                variant="plain">
              </v-text-field>
            </v-col>
          </v-row>
        </v-container>

        <ScheduleForm />
      </v-container>
    </template>

    <v-divider></v-divider>

    <v-card-actions class="bg-surface-light">
      <v-btn
        prepend-icon="mdi-content-save-off-outline"
        @click="scheduleStore.showFormDialog = false">
        Cancel
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        prepend-icon="mdi-content-save-outline"
        :disabled="!boolCanSave"
        @click="saveSchedule()">
        Save
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { debounce } from "lodash";

import ScheduleForm from "./ScheduleForm.vue";

import { formatTimestamp, parseDateTimeLocalToTimestamp } from "../../Common/time";
import { validateCronExpression } from "../../Schedule/cron";
import type { Dict_Detail_ScheduleForm } from "../../Schedule/types";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

const boolCanSave = ref(false);

const currentDetail = computed<Dict_Detail_ScheduleForm | undefined>(() => {
  if (scheduleStore.formMode === "new") {
    return scheduleStore.dictDetailNew;
  }
  if (scheduleStore.formMode === "edit") {
    return scheduleStore.dictDetailEdit;
  }
  return undefined;
});

const dialogTitle = computed(() =>
  scheduleStore.formMode === "new" ? "New Schedule" : "Edit Schedule",
);

const debouncedUpdateSaveState = debounce(() => {
  const detail = currentDetail.value;
  if (detail === undefined || !validateCronExpression(detail.cron).valid) {
    boolCanSave.value = false;
    return;
  }

  if (
    detail.name === "" ||
    detail.project_id === undefined ||
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
  currentDetail,
  () => {
    debouncedUpdateSaveState();
  },
  { deep: true, immediate: true },
);

onBeforeUnmount(() => {
  debouncedUpdateSaveState.cancel();
});

async function saveSchedule(): Promise<void> {
  if (scheduleStore.formMode === "new") {
    await scheduleStore.createSchedule();
    return;
  }

  if (scheduleStore.formMode === "edit") {
    await scheduleStore.saveSchedule();
  }
}
</script>

<style scoped></style>
