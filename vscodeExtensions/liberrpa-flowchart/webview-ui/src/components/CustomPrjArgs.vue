<!-- FileName: CustomPrjArgs.vue -->
<template>
  <v-container class="pa-1 ma-0 d-flex flex-column">
    <!-- Label -->
    <v-label class="pa-2 ma-0 text-center" style="display: block"
      >Custom Project Arguments</v-label
    >

    <!-- All argument inputboxes -->
    <v-container class="pa-0 ma-0 flex-grow-1 overflow-y-auto">
      <v-row
        v-for="(item, index) in argsStore.customPrjArgs"
        :key="index"
        class="pa-0 ma-0">
        <!-- The value name inputbox, should not have same name. -->
        <v-col cols="6" class="pa-0 ma-0">
          <!--
          The input field displays the surrounding double quotes as prefix and suffix.
          The user edits only the string content inside the quotes.
          -->
          <v-text-field
            v-model="arrKeyCache[index]"
            variant="underlined"
            density="comfortable"
            hide-details
            spellcheck="false"
            prepend-inner-icon="mdi-minus"
            :prefix="'&quot;'"
            :suffix="'&quot;'"
            :bg-color="generateBgcolor(item[0])"
            @blur="updateKey(index, arrKeyCache[index])"
            @keyup.enter="updateKey(index, arrKeyCache[index])"
            @click:prepend-inner="deleteArgument(index)">
            <v-tooltip
              v-if="generateBgcolor(item[0]) !== ''"
              activator="parent"
              location="top">
              Duplicate keys exist. At runtime, the last value with the same key takes
              effect.
            </v-tooltip>
          </v-text-field>
        </v-col>

        <!-- The equal symbol. -->
        <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

        <!-- The variable's value, it must can be deserialized. -->
        <v-col cols="5" class="pa-0 ma-0">
          <v-text-field
            v-model="arrValueCache[index]"
            variant="underlined"
            density="comfortable"
            hide-details
            spellcheck="false"
            @blur="updateValue(index, arrValueCache[index])"
            @keyup.enter="updateValue(index, arrValueCache[index])">
            <v-tooltip activator="parent" location="top">
              <div style="max-width: 560px">
                <div class="font-weight-medium mb-1">Original value:</div>

                <!-- Use <pre> to keep the format. -->
                <pre
                  class="pa-2 my-1"
                  style="white-space: pre-wrap; word-break: break-word"
                  v-text="stringifyValue(item[1])"></pre>

                <div>The value must be JSON-deserializable.</div>
                <div>Press Enter or leave the input box to update.</div>

                <div v-if="isPlainObject(item[1])" class="mt-1 font-italic">
                  It is an object. Object key order should not be relied on, and
                  integer-like keys may be reordered.
                </div>
              </div>
            </v-tooltip>
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>

    <!-- The add button. -->
    <v-btn class="w-100" variant="outlined" @click="addNewArgument">
      <v-tooltip activator="parent" location="top">
        Click to add a new custom argument.
      </v-tooltip>
      <v-icon icon="mdi-playlist-plus"></v-icon>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { useArgsStore } from "../store";
import type { StoreCustomPrjArg } from "../store";
import { showAlert, updateLocalData } from "../commonFunc";
import type { JsonValue, CustomPrjArg } from "../interface";

const argsStore = useArgsStore();

function stringifyKeyForInput(key: string): string {
  return JSON.stringify(key).slice(1, -1);
}

// Initialize localValues as an array of stringified item values
const arrKeyCache = ref<string[]>(
  argsStore.customPrjArgs.map(([key]) => stringifyKeyForInput(key))
);
const arrValueCache = ref<string[]>(
  argsStore.customPrjArgs.map((item: StoreCustomPrjArg) => JSON.stringify(item[1], null, 0))
);

const syncCustomPrjArgs = (): void => {
  arrKeyCache.value = argsStore.customPrjArgs.map(([key]) => stringifyKeyForInput(key));

  arrValueCache.value = argsStore.customPrjArgs.map(([, value]) => JSON.stringify(value));

  updateLocalData(
    null,
    null,
    null,
    null,
    null,
    null,
    toCustomPrjArgs(argsStore.customPrjArgs)
  );
};

watch(() => argsStore.customPrjArgs, syncCustomPrjArgs, { deep: true });

function toCustomPrjArgs(args: StoreCustomPrjArg[]): CustomPrjArg[] {
  return args.map(([name, value]) => [name, value as JsonValue]);
}

function generateBgcolor(valueName: string): string {
  const arrNames = argsStore.customPrjArgs.filter((arrIn) => {
    if (arrIn[0] === valueName) {
      return true;
    }
  });
  if (arrNames.length >= 2) {
    return "warning";
  }
  return "";
}

function updateKey(index: number, input: string): void {
  try {
    const parsedKey: unknown = JSON.parse(`"${input}"`);

    if (typeof parsedKey !== "string") {
      throw new TypeError("The custom argument key must be a string.");
    }

    // Avoid triggering Store updates when the key has not changed.
    if (argsStore.customPrjArgs[index][0] === parsedKey) {
      return;
    }

    argsStore.customPrjArgs[index][0] = parsedKey;
  } catch (error) {
    showAlert(
      `Invalid custom argument key: ${
        error instanceof Error ? error.message : String(error)
      }`
    );

    // Restore only the invalid key input.
    arrKeyCache.value[index] = stringifyKeyForInput(argsStore.customPrjArgs[index][0]);
  }
}

function updateValue(index: number, value: string): void {
  try {
    const parsedValue = JSON.parse(value) as JsonValue;
    argsStore.customPrjArgs[index][1] = parsedValue;
  } catch {
    showAlert(`It can't be deserialized: ${value}`);
    // Reset inputbox.
    arrValueCache.value = argsStore.customPrjArgs.map((item) =>
      JSON.stringify(item[1], null, 0)
    );
  }
}

function stringifyValue(value: unknown): string {
  const result = JSON.stringify(value, null, 0);

  if (result === undefined) {
    return String(value);
  }

  return result;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function addNewArgument(): void {
  argsStore.customPrjArgs.push(["", ""]);
  arrKeyCache.value.push("");
  arrValueCache.value.push('""');
}

function deleteArgument(index: number): void {
  argsStore.customPrjArgs.splice(index, 1);
  arrKeyCache.value.splice(index, 1);
  arrValueCache.value.splice(index, 1);
}
</script>

<style scoped></style>
