<!-- FileName: CustomArgumentsEditor.vue -->
<template>
  <v-container
    v-if="customArgs.length !== 0"
    fluid
    class="clean-space flex-column-grow-1 flex-column">
    <v-row
      v-for="(item, index) in customArgs"
      :key="index"
      class="clean-space w-100"
      style="max-height: 40px">
      <v-col cols="6" class="pa-0 ma-0">
        <v-text-field
          :model-value="item[0]"
          variant="plain"
          density="comfortable"
          hide-details
          readonly
          spellcheck="false"
          :bg-color="isDuplicateKey(item[0]) ? 'warning' : ''">
          <v-tooltip activator="parent" location="top">
            <template v-if="isDuplicateKey(item[0])">
              Duplicate keys exist. At runtime, the last value with the same key takes
              effect.
            </template>

            <template v-else>{{ item[0] }}</template>
          </v-tooltip>
        </v-text-field>
      </v-col>

      <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

      <v-col cols="5" class="pa-0 ma-0">
        <v-text-field
          v-model="arrValueCache[index]"
          variant="underlined"
          density="comfortable"
          hide-details
          spellcheck="false"
          @blur="updateValue(index)"
          @keyup.enter="updateValue(index)">
          <v-tooltip activator="parent" location="top">
            <span class="text-pre-line">{{ getArgumentValueNote(item[1]) }}</span>
          </v-tooltip>
        </v-text-field>
      </v-col>
    </v-row>
  </v-container>

  <v-container v-else fluid class="clean-space">No custom arguments.</v-container>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

import { useInformationStore } from "../../Store/informationStore";
import type { CustomProjectArgs } from "../../../../shared/runSettings";

const customArgs = defineModel<CustomProjectArgs>("customArgs", { required: true });

const arrValueCache = ref<string[]>([]);

function refreshValueCache(): void {
  arrValueCache.value = customArgs.value.map((item) => JSON.stringify(item[1], null, 0));
}

function isDuplicateKey(key: string): boolean {
  return customArgs.value.filter(([argumentKey]) => argumentKey === key).length >= 2;
}

function getArgumentValueNote(value: unknown): string {
  const strValue = JSON.stringify(value, null, 0) ?? "undefined";
  const arrLine = [
    "Current value:",
    strValue,
    "The value must be valid JSON.",
    "Press Enter or leave the input box to update.",
  ];
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    arrLine.push("Object keys may be reordered.");
  }
  return arrLine.join("\n");
}

function updateValue(index: number): void {
  const value = arrValueCache.value[index];
  if (value === undefined) {
    return;
  }

  const arrCustomArgs = customArgs.value.map(([name, argumentValue]): [string, unknown] => [
    name,
    argumentValue,
  ]);
  try {
    arrCustomArgs[index][1] = JSON.parse(value, (_key, argumentValue: unknown) => {
      if (typeof argumentValue === "number") {
        if (!Number.isFinite(argumentValue)) {
          throw new Error("Numbers must be finite.");
        }
        if (Number.isInteger(argumentValue) && !Number.isSafeInteger(argumentValue)) {
          throw new Error(
            "Integers must be between -9007199254740991 and 9007199254740991.",
          );
        }
      }
      return argumentValue;
    });
  } catch (e: unknown) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(
      e instanceof Error && !(e instanceof SyntaxError)
        ? e.message
        : "Enter a valid JSON value.",
    );
    arrValueCache.value[index] = JSON.stringify(arrCustomArgs[index][1]);
  }
  customArgs.value = arrCustomArgs;
}

watch(
  customArgs,
  () => {
    refreshValueCache();
  },
  { deep: true, immediate: true },
);
</script>

<style scoped>
:deep(input) {
  text-overflow: ellipsis;
}
</style>
