<!-- FileName: RunArgumentsEditor.vue -->
<template>
  <v-row>
    <v-col cols="12" md="6">
      <h3 class="text-subtitle-1 mb-3">Built-in Arguments</h3>

      <BuiltInArguments
        v-model="settings"
        :disabled="disabled"
        :readonly="readonly"
        :field-errors="fieldErrors">
        <template #environment>
          <slot name="environment" />
        </template>
      </BuiltInArguments>
    </v-col>

    <v-col cols="12" md="6" class="d-flex flex-column">
      <h3 class="text-subtitle-1 mb-3 flex-shrink-0">Custom Project Arguments</h3>

      <v-sheet :height="mdAndUp ? 0 : undefined" class="flex-grow-1 overflow-y-auto">
        <v-alert v-if="boolDuplicate" type="warning" variant="tonal" class="mb-3">
          Duplicate keys exist. At runtime, the last value with the same key takes effect.
        </v-alert>

        <v-alert v-if="strAssetError" type="error" variant="tonal" class="mb-3">
          {{ strAssetError }}
          <v-btn
            variant="tonal"
            prepend-icon="mdi-refresh"
            size="small"
            :disabled="disabled || boolLoadingAssets"
            @click="loadAssets">
            Retry
          </v-btn>
        </v-alert>

        <v-alert v-if="strArgumentsError" type="error" variant="tonal" class="mb-3">
          {{ strArgumentsError }}
        </v-alert>

        <v-alert
          v-if="fieldErrors?.['settings.custom_prj_args']"
          type="error"
          variant="tonal"
          class="mb-3">
          {{ fieldErrors?.["settings.custom_prj_args"]?.join(" ") }}
        </v-alert>

        <v-alert
          v-if="fieldErrors?.['settings.custom_arg_assets']"
          type="error"
          variant="tonal"
          class="mb-3">
          {{ fieldErrors?.["settings.custom_arg_assets"]?.join(" ") }}
        </v-alert>

        <p v-if="settings.custom_prj_args.length === 0" class="text-medium-emphasis">
          No custom arguments.
        </p>

        <v-row
          v-for="(argument, index) in settings.custom_prj_args"
          :key="index"
          no-gutters
          align="center"
          class="mb-2 flex-nowrap">
          <v-col cols="4" class="pr-2">
            <v-text-field
              :model-value="argument[0]"
              :aria-label="`Argument ${index + 1} name`"
              readonly
              variant="plain"
              density="compact"
              hide-details>
              <v-tooltip activator="parent" location="top">{{ argument[0] }}</v-tooltip>
            </v-text-field>
          </v-col>

          <v-col cols="auto" class="px-1" aria-hidden="true">=</v-col>

          <v-col cols="auto" class="px-3">
            <v-switch
              :model-value="!!settings.custom_arg_assets[index]"
              :aria-label="`Source for ${argument[0]}: ${settings.custom_arg_assets[index] ? 'Asset' : 'Value'}`"
              true-icon="mdi-database-outline"
              false-icon="mdi-code-json"
              density="compact"
              hide-details
              :disabled="disabled"
              :readonly="readonly"
              @update:model-value="setSource(index, $event === true)">
              <v-tooltip activator="parent" location="top">
                {{ settings.custom_arg_assets[index] ? "Asset" : "Value" }}
              </v-tooltip>
            </v-switch>
          </v-col>

          <v-col style="min-width: 0">
            <!-- NOTE: Use the short label due to container's width-->
            <v-select
              v-if="settings.custom_arg_assets[index]"
              :variant="readonly ? 'plain' : 'underlined'"
              :menu-icon="readonly ? '' : undefined"
              density="compact"
              :model-value="settings.custom_arg_assets[index]?.name"
              :items="arrAsset"
              item-title="name"
              item-value="name"
              label="(same dept, non-secret)"
              hide-details="auto"
              :error-messages="
                getFieldErrors(fieldErrors, `settings.custom_arg_assets.${index}`)
              "
              :disabled="disabled"
              :readonly="readonly"
              :loading="boolLoadingAssets"
              :rules="[(value) => !!value || 'Select an asset.']"
              @update:model-value="setAsset(index, $event)">
              <template #item="{ props: itemProps, item }">
                <v-list-item v-bind="itemProps" :subtitle="item.raw.asset_type" />
              </template>
            </v-select>

            <v-text-field
              v-else
              v-model="arrValue[index]"
              :variant="readonly ? 'plain' : 'underlined'"
              density="compact"
              :aria-label="`Value for ${argument[0]} (JSON)`"
              hide-details="auto"
              :disabled="disabled"
              :readonly="readonly"
              :error-messages="[
                ...(arrError[index] ? [arrError[index]!] : []),
                ...getFieldErrors(fieldErrors, `settings.custom_prj_args.${index}`),
              ]"
              spellcheck="false"
              @update:model-value="updateValue(index, $event)" />
          </v-col>
        </v-row>
      </v-sheet>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useDisplay } from "vuetify";

import BuiltInArguments from "./BuiltInArguments.vue";

import { getAssetList } from "@/api/assets";
import { getApiError, getFieldErrors } from "@/api/errors";
import type { AssetEntryResponse } from "@/api/generated/browserApi";

import type { JsonValue, RunSettings } from "@/api/runSettings";

import { validateJsonValue } from "@/app/validators";

const props = defineProps<{
  departmentId: string;
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();

const { mdAndUp } = useDisplay();

const INT_CUSTOM_ARGUMENT_MAX_COUNT = 100;
const settings = defineModel<RunSettings>({ required: true });
const emit = defineEmits<{ valid: [value: boolean] }>();

const arrValue = ref(
  settings.value.custom_prj_args.map((entry) => JSON.stringify(entry[1])),
);

const arrError = ref<string[]>([]);
const arrAsset = ref<AssetEntryResponse[]>([]);
const strAssetError = ref("");
const boolLoadingAssets = ref(false);
let intAssetRevision = 0;
let strAssetDepartmentId = "";
let boolAssetsLoaded = false;

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

function publishValid(): void {
  emit("valid", !strArgumentsError.value && arrError.value.every((value) => !value));
}

function updateValue(index: number, text: string): void {
  try {
    const value = JSON.parse(text, (_key, argumentValue: unknown) => {
      if (typeof argumentValue === "number") validateJsonValue(argumentValue);
      return argumentValue;
    }) as JsonValue;
    const argument = settings.value.custom_prj_args[index];
    if (argument) argument[1] = value;
    arrError.value[index] = "";
  } catch (e) {
    arrError.value[index] =
      e instanceof Error && !(e instanceof SyntaxError) ? e.message : "Enter valid JSON.";
  }
  publishValid();
}

function setSource(index: number, useAsset: boolean): void {
  settings.value.custom_arg_assets = settings.value.custom_prj_args.map(
    (_, intIndex) => settings.value.custom_arg_assets[intIndex] ?? null,
  );
  settings.value.custom_arg_assets[index] = useAsset
    ? { name: "", asset_type: "text" }
    : null;
  if (!useAsset) updateValue(index, arrValue.value[index] ?? "");
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
  const strDepartmentId = props.departmentId;
  if (strAssetDepartmentId !== strDepartmentId) {
    intAssetRevision += 1;
    strAssetDepartmentId = strDepartmentId;
    arrAsset.value = [];
    strAssetError.value = "";
    boolLoadingAssets.value = false;
    boolAssetsLoaded = false;
  }
  if (
    props.readonly ||
    !strDepartmentId ||
    !settings.value.custom_arg_assets.some((binding) => binding !== null) ||
    boolAssetsLoaded ||
    boolLoadingAssets.value
  )
    return;
  const intRevision = ++intAssetRevision;
  strAssetError.value = "";
  boolLoadingAssets.value = true;
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
    boolAssetsLoaded = true;
  } catch (e) {
    if (intRevision === intAssetRevision) strAssetError.value = getApiError(e).message;
  } finally {
    if (intRevision === intAssetRevision) boolLoadingAssets.value = false;
  }
}

watch(strArgumentsError, publishValid, { immediate: true });

watch(
  [
    () => props.departmentId,
    () => settings.value.custom_arg_assets.some((binding) => binding !== null),
  ],
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
