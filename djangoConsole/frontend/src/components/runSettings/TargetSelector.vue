<!-- FileName: TargetSelector.vue -->
<template>
  <v-row align="center">
    <v-col cols="12" md="6" class="d-flex align-center flex-wrap ga-2">
      <v-label :id="strLabelId" class="text-caption">Target Type</v-label>

      <v-radio-group
        v-model="strTargetType"
        inline
        :aria-labelledby="strLabelId"
        class="flex-grow-0"
        density="compact"
        hide-details="auto"
        :readonly="readonly"
        :disabled="disabled || boolLoading || !departmentId"
        @update:model-value="changeType">
        <v-radio label="Executors" :value="JobTargetType.Executor" />
        <v-radio label="Executor Group" :value="JobTargetType.Group" />
      </v-radio-group>
    </v-col>

    <v-col cols="12" md="6">
      <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
        {{ strError }}
        <v-btn
          variant="tonal"
          prepend-icon="mdi-refresh"
          size="small"
          :disabled="disabled || boolLoading"
          @click="loadTargets">
          Retry
        </v-btn>
      </v-alert>

      <v-select
        v-if="strTargetType === JobTargetType.Executor"
        v-model="executorIds"
        :variant="readonly ? 'plain' : 'underlined'"
        :menu-icon="readonly ? '' : undefined"
        density="compact"
        hide-details="auto"
        :items="arrExecutor"
        item-title="name"
        item-value="id"
        label="Executors"
        :no-data-text="
          strError ? 'Could not load Executors.' : 'No Executors in this department.'
        "
        :error-messages="getFieldErrors(fieldErrors, 'executor_ids')"
        multiple
        chips
        :closable-chips="!readonly"
        :loading="boolLoading"
        :readonly="readonly"
        :disabled="disabled || boolLoading || !departmentId"
        :rules="[(value) => value.length > 0 || 'Select at least one Executor.']">
        <template #item="{ props: itemProps, item }">
          <v-list-item
            v-bind="itemProps"
            :subtitle="`${item.raw.association_status} · ${item.raw.dispatch_enabled ? 'Dispatch enabled' : 'Paused'}`" />
        </template>
      </v-select>

      <v-select
        v-else
        v-model="groupId"
        :variant="readonly ? 'plain' : 'underlined'"
        :menu-icon="readonly ? '' : undefined"
        density="compact"
        hide-details="auto"
        :items="arrGroup"
        item-title="name"
        item-value="id"
        label="Executor Group"
        :no-data-text="
          strError ? 'Could not load groups.' : 'No Executor Groups in this department.'
        "
        :error-messages="getFieldErrors(fieldErrors, 'group_id')"
        :loading="boolLoading"
        :readonly="readonly"
        :disabled="disabled || boolLoading || !departmentId"
        :rules="[(value) => !!value || 'Select a group.']">
        <template #item="{ props: itemProps, item }">
          <v-list-item
            v-bind="itemProps"
            :subtitle="`${item.raw.member_count} members · ${item.raw.online_count} online`" />
        </template>
      </v-select>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, useId, watch } from "vue";

import { getRunTargetOptions } from "@/api/executors";
import { getApiError, getFieldErrors } from "@/api/errors";
import {
  JobTargetType,
  type ExecutorTargetOptionResponse,
  type ExecutorGroupTargetOptionResponse,
} from "@/api/generated/browserApi";

const props = defineProps<{
  departmentId: string;
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();

const executorIds = defineModel<string[]>("executorIds", { required: true });
const groupId = defineModel<string | null>("groupId", { required: true });

const strLabelId = useId();

const strTargetType = ref<JobTargetType>(
  groupId.value ? JobTargetType.Group : JobTargetType.Executor,
);
const arrExecutor = ref<ExecutorTargetOptionResponse[]>([]);
const arrGroup = ref<ExecutorGroupTargetOptionResponse[]>([]);
const boolLoading = ref(false);
const strError = ref("");
let intRevision = 0;

function changeType(): void {
  executorIds.value = [];
  groupId.value = null;
}

async function loadTargets(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  const strDepartmentId = props.departmentId;
  arrExecutor.value = [];
  arrGroup.value = [];
  strError.value = "";
  boolLoading.value = !!strDepartmentId;
  if (!strDepartmentId) return;
  try {
    const response = await getRunTargetOptions(strDepartmentId);
    if (intCurrentRevision !== intRevision) return;
    arrExecutor.value = response.executors;
    arrGroup.value = response.executor_groups;
  } catch (e) {
    if (intRevision === intCurrentRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intCurrentRevision) boolLoading.value = false;
  }
}

// A Schedule may supply its saved target after this component has mounted.
watch(groupId, (value) => {
  if (value !== null) strTargetType.value = JobTargetType.Group;
});

watch(executorIds, (value) => {
  if (value.length) strTargetType.value = JobTargetType.Executor;
});

watch(
  () => props.departmentId,
  () => void loadTargets(),
  { immediate: true },
);

onBeforeUnmount(() => {
  intRevision++;
});
</script>

<style scoped></style>
