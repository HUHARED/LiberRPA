<!-- FileName: TargetSelector.vue -->
<template>
  <v-radio-group
    v-model="strTargetType"
    inline
    label="Target Type"
    :disabled="disabled || boolLoading || !departmentId"
    @update:model-value="changeType">
    <v-radio label="Executors" value="executor" />
    <v-radio label="Executor Group" value="group" />
  </v-radio-group>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
    {{ strError }}
    <v-btn
      variant="tonal"
      size="small"
      :disabled="disabled || boolLoading"
      @click="loadTargets">
      Retry
    </v-btn>
  </v-alert>
  <v-select
    v-if="strTargetType === 'executor'"
    v-model="executorIds"
    variant="underlined"
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
    closable-chips
    :loading="boolLoading"
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
    variant="underlined"
    :items="arrGroup"
    item-title="name"
    item-value="id"
    label="Executor Group"
    :no-data-text="
      strError ? 'Could not load groups.' : 'No Executor Groups in this department.'
    "
    :error-messages="getFieldErrors(fieldErrors, 'group_id')"
    :loading="boolLoading"
    :disabled="disabled || boolLoading || !departmentId"
    :rules="[(value) => !!value || 'Select a group.']">
    <template #item="{ props: itemProps, item }">
      <v-list-item
        v-bind="itemProps"
        :subtitle="`${item.raw.member_count} members · ${item.raw.online_count} online`" />
    </template>
  </v-select>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { getExecutorList } from "@/api/executors";
import { getExecutorGroupList } from "@/api/executorGroups";
import { getApiError, getFieldErrors } from "@/api/errors";
import type {
  ExecutorListEntryResponse,
  ExecutorGroupListEntryResponse,
} from "@/api/generated/browserApi";
const props = defineProps<{
  departmentId: string;
  disabled?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();
const executorIds = defineModel<string[]>("executorIds", { required: true });
const groupId = defineModel<string | null>("groupId", { required: true });
type TargetType = "executor" | "group";
const strTargetType = ref<TargetType>(groupId.value ? "group" : "executor");
const arrExecutor = ref<ExecutorListEntryResponse[]>([]);
const arrGroup = ref<ExecutorGroupListEntryResponse[]>([]);
const boolLoading = ref(false);
const strError = ref("");
let intRevision = 0;
let strLoadedDepartmentId = "";
let boolExecutorsLoaded = false;
let boolGroupsLoaded = false;

function changeType(): void {
  executorIds.value = [];
  groupId.value = null;
}

async function loadTargets(): Promise<void> {
  const intCurrentRevision = ++intRevision;
  const strDepartmentId = props.departmentId;
  const strRequestedType = strTargetType.value;
  if (strLoadedDepartmentId !== strDepartmentId) {
    strLoadedDepartmentId = strDepartmentId;
    arrExecutor.value = [];
    arrGroup.value = [];
    boolExecutorsLoaded = false;
    boolGroupsLoaded = false;
  }
  strError.value = "";
  boolLoading.value = false;
  if (
    !strDepartmentId ||
    (strRequestedType === "executor" ? boolExecutorsLoaded : boolGroupsLoaded)
  )
    return;
  boolLoading.value = true;
  try {
    let intPage = 1;
    let intTotalPages = 1;
    if (strRequestedType === "executor") {
      const arrResult: ExecutorListEntryResponse[] = [];
      do {
        const result = await getExecutorList(
          { name: "", departmentIds: [strDepartmentId], dispatchStates: [] },
          intPage++,
        );
        if (intCurrentRevision !== intRevision) return;
        arrResult.push(...result.executors);
        intTotalPages = result.total_pages;
      } while (intPage <= intTotalPages);
      arrExecutor.value = arrResult;
      boolExecutorsLoaded = true;
    } else {
      const arrResult: ExecutorGroupListEntryResponse[] = [];
      do {
        const result = await getExecutorGroupList(
          { name: "", departmentIds: [strDepartmentId] },
          intPage++,
        );
        if (intCurrentRevision !== intRevision) return;
        arrResult.push(...result.executor_groups);
        intTotalPages = result.total_pages;
      } while (intPage <= intTotalPages);
      arrGroup.value = arrResult;
      boolGroupsLoaded = true;
    }
  } catch (e) {
    if (intRevision === intCurrentRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intCurrentRevision) boolLoading.value = false;
  }
}

// A Schedule may supply its saved target after this component has mounted.
watch(groupId, (value) => {
  if (value !== null) strTargetType.value = "group";
});
watch(executorIds, (value) => {
  if (value.length) strTargetType.value = "executor";
});
watch([() => props.departmentId, strTargetType], () => void loadTargets(), {
  immediate: true,
});
onBeforeUnmount(() => {
  intRevision++;
});
</script>
<style scoped></style>
