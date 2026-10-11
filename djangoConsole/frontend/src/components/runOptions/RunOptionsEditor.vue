<!-- FileName: RunOptionsEditor.vue -->
<template>
  <v-row>
    <v-col cols="12" sm="4">
      <v-number-input
        v-model="settings.max_retry_count"
        label="Max Retry Count"
        :min="0"
        :max="3"
        :precision="0"
        :rules="[validateMaxRetryCount]"
        :disabled="disabled"
        hint="Maximum extra attempts after an execution error."
        persistent-hint />
    </v-col>
    <v-col cols="12" sm="4">
      <v-number-input
        v-model="settings.timeout_min"
        label="Timeout (min)"
        :min="0"
        :max="INT_MAX_TIMEOUT_MIN"
        :precision="0"
        :rules="[validateTimeout]"
        :disabled="disabled"
        hint="0 means no limit. Applies to each attempt."
        persistent-hint />
    </v-col>
    <v-col cols="12" sm="4">
      <v-select
        v-model="settings.builtin_log_level"
        label="Log Level"
        :items="ARR_LOG_LEVEL"
        :disabled="disabled" />
    </v-col>
  </v-row>
  <v-row>
    <v-col cols="12" sm="4">
      <v-switch
        v-model="settings.builtin_record_video"
        label="Record Video"
        hide-details
        :disabled="disabled" />
    </v-col>
    <v-col cols="12" sm="4">
      <v-switch
        v-model="settings.builtin_stop_shortcut"
        label="Stop Shortcut"
        hide-details
        :disabled="disabled" />
    </v-col>
    <v-col cols="12" sm="4">
      <v-switch
        v-model="settings.builtin_highlight_ui"
        label="Highlight UI"
        hide-details
        :disabled="disabled" />
    </v-col>
  </v-row>
  <h3 class="text-subtitle-1 mt-5 mb-3">Custom Arguments</h3>
  <v-alert v-if="boolDuplicate" type="warning" variant="tonal" class="mb-3">
    Duplicate keys exist. At runtime, the last value with the same key takes effect.
  </v-alert>
  <v-alert v-if="strAssetError" type="error" variant="tonal" class="mb-3">
    {{ strAssetError }}
  </v-alert>
  <v-alert v-if="strArgumentsError" type="error" variant="tonal" class="mb-3">
    {{ strArgumentsError }}
  </v-alert>
  <p v-if="settings.custom_prj_args.length === 0" class="text-medium-emphasis">
    No custom arguments.
  </p>
  <v-row v-for="(argument, index) in settings.custom_prj_args" :key="index" align="start">
    <v-col cols="12" md="3">
      <v-text-field :model-value="argument[0]" label="Key" readonly variant="plain" />
    </v-col>
    <v-col cols="12" md="3">
      <v-select
        :model-value="settings.custom_arg_assets[index] ? 'asset' : 'value'"
        :items="ARR_SOURCE"
        label="Source"
        :disabled="disabled"
        @update:model-value="setSource(index, $event)" />
    </v-col>
    <v-col cols="12" md="6">
      <v-select
        v-if="settings.custom_arg_assets[index]"
        :model-value="settings.custom_arg_assets[index]?.name"
        :items="arrAsset"
        item-title="name"
        item-value="name"
        label="Asset (same department)"
        :disabled="disabled"
        :loading="boolLoadingAssets"
        :rules="[(value) => !!value || 'Select an asset.']"
        @update:model-value="setAsset(index, $event)">
        <template #item="{ props: itemProps, item }">
          <v-list-item v-bind="itemProps" :subtitle="item.raw.asset_type" />
        </template>
      </v-select>
      <v-textarea
        v-else
        v-model="arrValue[index]"
        label="Value (JSON)"
        rows="1"
        auto-grow
        :disabled="disabled"
        :error-messages="arrError[index]"
        spellcheck="false"
        @update:model-value="updateValue(index, $event)" />
    </v-col>
  </v-row>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import { getAssetList } from "@/api/assets";
import { getApiError } from "@/api/errors";
import type { AssetEntryResponse } from "@/api/generated/browserApi";

import { validateJsonValue } from "@/app/validators";

import {
  type JsonValue,
  type RunSettings,
  ARR_LOG_LEVEL,
  INT_MAX_TIMEOUT_MIN,
} from "@/api/runOptions";

const props = defineProps<{ departmentId: string; disabled?: boolean }>();
const INT_CUSTOM_ARGUMENT_MAX_COUNT = 100;
const settings = defineModel<RunSettings>({ required: true });
const emit = defineEmits<{ valid: [value: boolean] }>();
const ARR_SOURCE = [
  { title: "Value", value: "value" },
  { title: "Asset", value: "asset" },
];
const arrValue = ref(
  settings.value.custom_prj_args.map((entry) => JSON.stringify(entry[1])),
);
const arrError = ref<string[]>([]);
const arrAsset = ref<AssetEntryResponse[]>([]);
const strAssetError = ref("");
const boolLoadingAssets = ref(false);
let intAssetRevision = 0;
const boolDuplicate = computed(
  () =>
    new Set(settings.value.custom_prj_args.map((entry) => entry[0])).size !==
    settings.value.custom_prj_args.length,
);
const strArgumentsError = computed(() => {
  // Validate the whole ordered-pair array, including values with asset bindings.
  const arrArguments = settings.value.custom_prj_args;
  try {
    if (arrArguments.length > INT_CUSTOM_ARGUMENT_MAX_COUNT)
      throw new Error(
        `Custom Arguments must not contain more than ${INT_CUSTOM_ARGUMENT_MAX_COUNT} entries.`,
      );
    validateJsonValue(arrArguments);
    if (new TextEncoder().encode(JSON.stringify(arrArguments)).length > 64 * 1024)
      throw new Error("Custom Arguments exceed the 64 KiB JSON limit.");
    return "";
  } catch (e) {
    return e instanceof Error ? e.message : "Enter valid Custom Arguments.";
  }
});

function validateMaxRetryCount(value: unknown): true | string {
  return (
    (typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 3) ||
    "Enter an integer from 0 to 3."
  );
}

function validateTimeout(value: unknown): true | string {
  return (
    (typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= INT_MAX_TIMEOUT_MIN) ||
    `Enter an integer from 0 to ${INT_MAX_TIMEOUT_MIN}.`
  );
}

function publishValid(): void {
  emit("valid", !strArgumentsError.value && arrError.value.every((value) => !value));
}

function updateValue(index: number, text: string): void {
  try {
    const value = JSON.parse(text) as JsonValue;
    const argument = settings.value.custom_prj_args[index];
    if (argument) argument[1] = value;
    arrError.value[index] = "";
  } catch {
    arrError.value[index] =
      'Enter valid JSON, for example "text", 12, true, null, [] or {}.';
  }
  publishValid();
}

function setSource(index: number, source: string): void {
  settings.value.custom_arg_assets = settings.value.custom_prj_args.map(
    (_, intIndex) => settings.value.custom_arg_assets[intIndex] ?? null,
  );
  settings.value.custom_arg_assets[index] =
    source === "asset" ? { name: "", asset_type: "text" } : null;
  if (source === "value") updateValue(index, arrValue.value[index] ?? "");
  else {
    arrError.value[index] = "";
    publishValid();
  }
}

function setAsset(index: number, name: string): void {
  const asset = arrAsset.value.find((entry) => entry.name === name);
  if (asset && asset.asset_type !== "secret_text" && asset.asset_type !== "credential")
    settings.value.custom_arg_assets[index] = {
      name: asset.name,
      asset_type: asset.asset_type,
    };
}

async function loadAssets(): Promise<void> {
  const intRevision = ++intAssetRevision;
  const strDepartmentId = props.departmentId;
  arrAsset.value = [];
  strAssetError.value = "";
  boolLoadingAssets.value = !!strDepartmentId;
  if (!strDepartmentId || !settings.value.custom_prj_args.length) {
    boolLoadingAssets.value = false;
    return;
  }
  try {
    const arrResult: AssetEntryResponse[] = [];
    let intPage = 1;
    let intTotalPages = 1;
    do {
      const result = await getAssetList(
        {
          name: "",
          departmentIds: [strDepartmentId],
          assetTypes: ["text", "integer", "number", "boolean", "json"],
        },
        intPage++,
      );
      if (intRevision !== intAssetRevision) return;
      arrResult.push(...result.assets);
      intTotalPages = result.total_pages;
    } while (intPage <= intTotalPages);
    arrAsset.value = arrResult;
  } catch (e) {
    if (intRevision === intAssetRevision) strAssetError.value = getApiError(e).message;
  } finally {
    if (intRevision === intAssetRevision) boolLoadingAssets.value = false;
  }
}

watch(strArgumentsError, publishValid, { immediate: true });

watch(
  [() => props.departmentId, () => settings.value.custom_prj_args.length > 0],
  () => void loadAssets(),
  { immediate: true },
);

watch(
  () => settings.value,
  () => {
    arrValue.value = settings.value.custom_prj_args.map((entry) =>
      JSON.stringify(entry[1]),
    );
    arrError.value = [];
    publishValid();
  },
);

onBeforeUnmount(() => {
  intAssetRevision += 1;
});
</script>
<style scoped></style>
