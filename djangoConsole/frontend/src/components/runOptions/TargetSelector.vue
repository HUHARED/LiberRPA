<!-- FileName: TargetSelector.vue -->
<template>
  <v-radio-group
    v-model="strTargetType"
    inline
    label="Target Type"
    :disabled="disabled"
    @update:model-value="changeType">
    <v-radio label="Executors" value="executor" />
    <v-radio label="Executor Group" value="group" />
  </v-radio-group>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
    {{ strError }}
  </v-alert>
  <v-select
    v-if="strTargetType === 'executor'"
    v-model="executorIds"
    :items="arrExecutor"
    item-title="name"
    item-value="id"
    label="Executors"
    multiple
    chips
    closable-chips
    :loading="boolLoading"
    :disabled="disabled"
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
    :items="arrGroup"
    item-title="name"
    item-value="id"
    label="Executor Group"
    :loading="boolLoading"
    :disabled="disabled"
    :rules="[(value) => !!value || 'Select a group.']">
    <template #item="{ props: itemProps, item }">
      <v-list-item
        v-bind="itemProps"
        :subtitle="`${item.raw.member_count} members · ${item.raw.online_count} online`" />
    </template>
  </v-select>
  <p class="text-body-2 text-medium-emphasis">
    Offline or paused Executors and empty groups can be saved. Availability is checked when
    dispatching.
  </p>
</template>
<script setup lang="ts">
import { ref, watch } from "vue";
import { getExecutorList } from "@/api/executors";
import { getExecutorGroupList } from "@/api/executorGroups";
import { getApiError } from "@/api/errors";
import type {
  ExecutorListEntryResponse,
  ExecutorGroupListEntryResponse,
} from "@/api/generated/browserApi";
const props = defineProps<{ departmentId: string; disabled?: boolean }>();
const executorIds = defineModel<string[]>("executorIds", { required: true });
const groupId = defineModel<string | null>("groupId", { required: true });
const strTargetType = ref(groupId.value ? "group" : "executor");
const arrExecutor = ref<ExecutorListEntryResponse[]>([]);
const arrGroup = ref<ExecutorGroupListEntryResponse[]>([]);
const boolLoading = ref(false);
const strError = ref("");
let intRevision = 0;
function changeType(): void {
  executorIds.value = [];
  groupId.value = null;
}
async function loadTargets(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  if (!props.departmentId) {
    arrExecutor.value = [];
    arrGroup.value = [];
    return;
  }
  boolLoading.value = true;
  strError.value = "";
  try {
    const [arrExecutorResult, arrGroupResult] = await Promise.all([
      (async (): Promise<ExecutorListEntryResponse[]> => {
        const arrResult: ExecutorListEntryResponse[] = [];
        let intPage = 1;
        let intTotal: number;
        do {
          const result = await getExecutorList(
            { name: "", departmentIds: [props.departmentId], dispatchStates: [] },
            intPage++,
          );
          arrResult.push(...result.executors);
          intTotal = result.total_pages;
        } while (intPage <= intTotal);
        return arrResult;
      })(),
      (async (): Promise<ExecutorGroupListEntryResponse[]> => {
        const arrResult: ExecutorGroupListEntryResponse[] = [];
        let intPage = 1;
        let intTotal: number;
        do {
          const result = await getExecutorGroupList(
            { name: "", departmentIds: [props.departmentId] },
            intPage++,
          );
          arrResult.push(...result.executor_groups);
          intTotal = result.total_pages;
        } while (intPage <= intTotal);
        return arrResult;
      })(),
    ]);
    if (intRevision === intCurrentRevision) {
      arrExecutor.value = arrExecutorResult;
      arrGroup.value = arrGroupResult;
    }
  } catch (e) {
    if (intRevision === intCurrentRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intCurrentRevision) boolLoading.value = false;
  }
}
watch(
  () => props.departmentId,
  () => void loadTargets(),
  { immediate: true },
);
</script>
<style scoped></style>
